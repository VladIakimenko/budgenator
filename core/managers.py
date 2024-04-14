from __future__ import annotations

import decimal
import logging
import functools
from typing import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

import config
from core.models import (
    Chat,
    State,
    Budget,
    Message,
    PeriodicTask,
    ScheduleBasis,
    ScheduleEntry,
    CrontabSchedule,
)
from core.utils import generate_trace_phrase, singleton

__all__ = [
    "ChatManager",
    "ScheduleBasis",
    "service_keeper",
]

logger = logging.getLogger(__name__)


class ManagerFactory(type):
    """
    A custom metaclass designed to secure managers' methods execution
    by wrapping each method into a try-except block with robust exception handling.
    """
    def __new__(cls, name, bases, dct):
        for attr, value in dct.items():
            if callable(value):
                dct[attr] = cls.handle_exceptions(value)
        return super().__new__(cls, name, bases, dct)

    @classmethod
    def handle_exceptions(cls, method: Callable):
        @functools.wraps(method)
        def wrapped(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except Exception as e:
                instance = args[0]
                log_message = (
                    f"\n"
                    f"\tException occurred during the '{type(instance).__name__}.{method.__name__}' execution:\n"
                    f"\targs: {[str(a) for a in args]}\n"
                    f"\tkwargs: {[f'{k}={v!s}' for k, v in kwargs.items()]}\n"
                    f"\texception: {e}"
                )
                # rollback
                getattr(instance, "db_session").rollback()
                # inform user that there was an error
                chat_id = self.chat_id
                if chat_id is not None:
                    from main import telegram_bot

                    trace_phrase = generate_trace_phrase()
                    log_message = "\n".join([log_message, f"\ttrace_phrase: '{trace_phrase}'"])
                    text = service_keeper.get_message("error", "info")
                    contacts = service_keeper.get_message("error", "contacts")
                    text = "\n".join([text, trace_phrase, contacts])
                    telegram_bot.send_message(chat_id=chat_id, text=text)
                # log the exception
                logger.error(log_message)
        return wrapped


class ChatManager(metaclass=ManagerFactory):
    db_session = sessionmaker(bind=config.core_engine)()

    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.schedule_manager = ScheduleManager(chat_manager=self)

    def _check_state(self) -> bool:
        state = self.db_session.execute(
            select(Chat.state).where(Chat.chat_id == self.chat_id)
        ).scalar()
        match state:
            case State.CONFIGURED:
                return True
            case State.INITIAL:
                # TODO: send message, that configuration is required for this operation
                logger.info(
                    f"BudgetController._state_check failed. "
                    f"The chat with {self.chat_id=} is not configured. "
                    f"The user has been informed"
                )
                return False

            case State.TERMINATED:
                # TODO: send message, that the budget accounting has been seized, remove the chat and start a new one
                logger.info(
                    f"Attempt to revoke the terminated chat with {self.chat_id=}. "
                    f"The user has been advised to start a new one"
                )
                return False

    def engage(
        self,
        replenishment: decimal.Decimal,
        start_balance: decimal.Decimal = None,
    ) -> None:
        chat = Chat()
        chat.chat_id = self.chat_id
        chat.latest_msg_received_at = datetime.now()

        budget = Budget()
        budget.chat_id = self.chat_id
        budget.replenishment = replenishment
        if start_balance:
            budget.balance = start_balance

        chat.budget = budget

        self.db_session.add_all([chat, budget])
        self.db_session.commit()

    def get_balance(self) -> decimal.Decimal | None:
        if not self._check_state():
            return
        return self.db_session.execute(
            select(Budget.balance)
            .where(Budget.chat_id == self.chat_id)
        ).scalar()

    def spend(self, amount: decimal.Decimal) -> None:
        if not self._check_state():
            return
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=Budget.balance - amount)
        )
        self.db_session.commit()

    def top_up(self, amount: decimal.Decimal = None) -> None:
        if not self._check_state():
            return
        replenishment = amount or Budget.replenishment
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=Budget.balance + replenishment)
        )
        self.db_session.commit()

    def annul(self) -> None:
        if not self._check_state():
            return
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=0)
        )
        self.db_session.commit()

    def change_replenishment(self, size: decimal.Decimal):
        if not self._check_state():
            return
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(replenishment=size)
        )
        self.db_session.commit()

    def refresh_latest_contact(self) -> None:
        self.db_session.execute(
            update(Chat)
            .where(Chat.chat_id == self.chat_id)
            .values(latest_contact=datetime.now())
        )
        self.db_session.commit()

    def set_configured(self) -> None:
        self.db_session.execute(
            update(Chat)
            .where(Chat.chat_id == self.chat_id)
            .values(state=State.CONFIGURED)
        )
        self.db_session.commit()

    def set_terminated(self) -> None:
        self.db_session.execute(
            update(Chat)
            .where(Chat.chat_id == self.chat_id)
            .values(state=State.TERMINATED)
        )
        # TODO add relevant objects removal
        self.db_session.commit()

    def add_scheduler_objects_pair(self, scheduler_id: int, task_id: int) -> None:
        chat = self.db_session.get(Chat, self.chat_id)
        chat.schedule_ids.append(scheduler_id)
        flag_modified(chat, "schedule_ids")
        chat.task_ids.append(task_id)
        flag_modified(chat, "task_ids")
        self.db_session.commit()


class ScheduleManager(metaclass=ManagerFactory):
    db_session = sessionmaker(bind=config.schedule_engine)()

    def __init__(self, chat_manager: ChatManager):
        self.chat_manager = chat_manager
        self.chat_id = chat_manager.chat_id

    def schedule_crontab_task(
        self, record: ScheduleEntry, chat_id: int = None
    ) -> None:
        """
        Uses ScheduleEntry objects to schedule crontab-based events
        (the events that are appointed to certain time, weekdays or monthdays)
        by means of forming the relevant schedule db objects, consumed by celery beat.

        params:
        record: ScheduleEntry data transfer objects, holding info on when should the task be executed
        task: str path to the task definition, like 'task_manager.tasks.sample_task'
        chat_id: int chat_id derived from pyTelegramBotAPI
        """
        if chat_id is None and record.event_type.requires_chat_id:
            raise TypeError(
                f"The events of type {record.event_type} require the 'chat_id' to be scheduled"
            )

        # create schedule db objects
        crontab_schedule = CrontabSchedule()
        crontab_schedule.minute = record.time.minute
        crontab_schedule.hour = record.time.hour
        if record.basis == ScheduleBasis.DAY_OF_THE_WEEK:
            crontab_schedule.day_of_week = record.day.ordinal_number
        elif record.basis == ScheduleBasis.DAY_OF_THE_MONTH:
            crontab_schedule.day_of_month = record.day
        crontab_schedule.timezone = config.TIMEZONE

        periodic_task = PeriodicTask()
        periodic_task.name = f"{record.event_type}_{chat_id}"
        periodic_task.task = record.event_type.task
        periodic_task.crontab = crontab_schedule

        self.db_session.add_all([crontab_schedule, periodic_task])
        self.db_session.commit()

        # assign the schedule db objects' ids to the chat
        if record.event_type.requires_chat_id:
            self.db_session.refresh(crontab_schedule)
            self.db_session.refresh(periodic_task)
            self.chat_manager.add_scheduler_objects_pair(crontab_schedule.id, periodic_task.id)


@singleton
class ServiceKeeper:
    core_session = sessionmaker(bind=config.core_engine)()
    schedule_session = sessionmaker(bind=config.schedule_engine)()

    def collect_ids_for_termination(self) -> tuple[list[int], list[int], list[int]]:
        """
        Collects the ids of all database objects that need to be cleared for the abandoned chats.
        """
        data = self.core_session.execute(
            select(Chat.chat_id, Chat.schedule_ids, Chat.task_ids)
            .where(datetime.now() - Chat.latest_contact > timedelta(days=config.MAX_IDLE_DAYS))
        ).all()
        chat_ids = []
        schedule_ids = []
        tasks_ids = []
        if data:
            for row in data:
                chat_ids.append(row[0])
                schedule_ids.extend(row[1])
                tasks_ids.extend(row[2])
        return chat_ids, schedule_ids, tasks_ids

    def batch_terminate(self, chat_ids: list[int]) -> None:
        """
        Set "TERMINATED" state for the chats with given ids, and remove related budgets
        """
        self.core_session.execute(
            update(Chat)
            .where(Chat.chat_id.in_(chat_ids))
            .values(state=State.TERMINATED)
        )
        self.core_session.execute(
            delete(Budget)
            .where(Budget.chat_id.in_(chat_ids))
        )
        self.core_session.commit()

    def batch_delete_schedule_objects(self, schedule_ids: list[int], task_ids: list[int]) -> None:
        self.schedule_session.execute(
            delete(CrontabSchedule)
            .where(CrontabSchedule.id.in_(schedule_ids))
        )
        self.schedule_session.execute(
            delete(PeriodicTask)
            .where(PeriodicTask.id.in_(task_ids))
        )
        self.schedule_session.commit()

    def get_message(self, section: str, alias: str) -> Message:
        try:
            message = self.core_session.get(Message, (section, alias)).value
        except AttributeError as e:
            logger.error(f"Could load message {section=}, {alias=}.\nException: {e}")
            message = config.CRITICAL_ERROR_MSG
        return message

    def upsert_message(self, section, alias, value):
        new_message = Message(section=section, alias=alias, value=value)
        self.core_session.merge(new_message)
        self.core_session.commit()


service_keeper = ServiceKeeper()
