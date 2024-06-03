from __future__ import annotations

import decimal
import logging
import functools
from json import dumps
from typing import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

# Project
import config
from core.utils import generate_trace_phrase
from core.models import (Chat,
                         Event,
                         State,
                         Budget,
                         Message,
                         PeriodicTask,
                         ScheduleBasis,
                         ScheduleEntry,
                         CrontabSchedule,)

__all__ = [
    "ChatManager",
    "ScheduleBasis",
    "service_keeper",
]

logger = logging.getLogger(__name__)


class ExceptionsHandlerMeta(type):
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
                instance = self
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
                    # Project
                    from main import telegram_bot

                    trace_phrase = generate_trace_phrase()
                    log_message = "\n".join([log_message, f"\ttrace_phrase: '{trace_phrase}'"])
                    text = service_keeper.get_message("error", "info")
                    contacts = service_keeper.get_message("error", "contacts")
                    text = "\n".join([text, trace_phrase, contacts])
                    telegram_bot.telebot.send_message(chat_id=chat_id, text=text)
                # log the exception
                logger.error(log_message)
        return wrapped


class ChatManager(metaclass=ExceptionsHandlerMeta):
    db_session = sessionmaker(bind=config.core_engine)()

    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.scheduler = Scheduler(chat_manager=self)

    def get_state(self) -> State:
        state = self.db_session.execute(
            select(Chat.state).where(Chat.chat_id == self.chat_id)
        ).scalar()
        if state == State.TERMINATED:
            logger.info(f"Attempt to revoke the terminated chat with {self.chat_id=}.")
        return state

    def set_configured(self) -> None:
        chat = self.db_session.get(Chat, self.chat_id)
        if chat.state == State.INITIAL:
            chat.state = State.CONFIGURED
            self.db_session.commit()
            logger.info(f"The state of the chat with chat_id {self.chat_id} is set to {State.CONFIGURED.value}.")

    def engage(
        self,
        start_balance: decimal.Decimal = None,
    ) -> None:
        chat = Chat()
        chat.chat_id = self.chat_id
        chat.latest_contact = datetime.now()

        budget = Budget()
        budget.chat_id = self.chat_id
        if start_balance is not None:
            budget.balance = start_balance

        chat.budget = budget

        self.db_session.add_all([chat, budget])
        self.db_session.commit()

    def get_balance(self) -> decimal.Decimal | None:
        return self.db_session.execute(
            select(Budget.balance)
            .where(Budget.chat_id == self.chat_id)
        ).scalar()

    def spend(self, amount: decimal.Decimal) -> None:
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=Budget.balance - amount)
        )
        self.db_session.commit()

    def top_up(self, amount: decimal.Decimal = None) -> None:
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=Budget.balance + amount)
        )
        self.db_session.commit()

    def annul(self) -> None:
        self.db_session.execute(
            update(Budget)
            .where(Budget.chat_id == self.chat_id)
            .values(balance=0)
        )
        self.db_session.commit()

    def refresh_latest_contact(self) -> None:
        self.db_session.execute(
            update(Chat)
            .where(Chat.chat_id == self.chat_id)
            .values(latest_contact=datetime.now())
        )
        self.db_session.commit()

    def add_event(self, record: ScheduleEntry, **kwargs) -> None:
        schedule, task = self.scheduler.schedule_crontab_task(record)
        event = Event(
            event_type=record.event_type,
            chat_id=self.chat_id,
            schedule_id=schedule.id,
            task_id=task.id,
            **kwargs    # used for concrete event-specific fields
        )
        self.db_session.add(event)
        self.db_session.commit()


class Scheduler(metaclass=ExceptionsHandlerMeta):
    db_session = sessionmaker(bind=config.schedule_engine)()

    def __init__(self, chat_manager: ChatManager):
        self.chat_manager = chat_manager
        self.chat_id = chat_manager.chat_id

    def schedule_crontab_task(
        self, record: ScheduleEntry
    ) -> tuple[CrontabSchedule, PeriodicTask]:
        """
        Uses ScheduleEntry objects to schedule crontab-based events
        (the events that are appointed to certain time, weekdays or monthdays)
        by means of forming the relevant schedule db objects, consumed by celery beat.

        params:
        record: ScheduleEntry data transfer objects, holding info on when should the task be executed
        task: str path to the task definition, like 'task_manager.tasks.sample_task'
        chat_id: int chat_id derived from pyTelegramBotAPI
        """

        crontab_schedule = CrontabSchedule()
        crontab_schedule.minute = record.time.minute
        crontab_schedule.hour = record.time.hour
        if record.basis == ScheduleBasis.DAY_OF_THE_WEEK:
            crontab_schedule.day_of_week = record.day.ordinal_number
        elif record.basis == ScheduleBasis.DAY_OF_THE_MONTH:
            crontab_schedule.day_of_month = record.day
        crontab_schedule.timezone = config.TIMEZONE

        periodic_task = PeriodicTask()
        periodic_task.name = f"{record.event_type.value}_{self.chat_id}_{datetime.now().timestamp()}"
        periodic_task.task = record.event_type.task
        periodic_task.crontab = crontab_schedule
        periodic_task.args = dumps([self.chat_id])

        self.db_session.add_all([crontab_schedule, periodic_task])
        self.db_session.commit()
        self.db_session.refresh(crontab_schedule)
        self.db_session.refresh(periodic_task)
        return crontab_schedule, periodic_task


class ServiceKeeper:
    core_session = sessionmaker(bind=config.core_engine)()
    schedule_session = sessionmaker(bind=config.schedule_engine)()

    def terminate_idle(self):
        """
        Deletes all db objects that need to be cleared for the abandoned chats,
        sets the chat's state to 'TERMINATED'
        """
        logger.info(f"Starting terminating idle chats...")
        data = self.core_session.execute(
            select(
                Chat.chat_id,
                Budget.budget_id,
                Event.event_id,
                Event.schedule_id,
                Event.task_id,
            )
            .select_from(Chat)
            .outerjoin(Chat.budget)
            .outerjoin(Chat.events)
            .where(datetime.now() - Chat.latest_contact > timedelta(days=config.MAX_IDLE_DAYS))
        ).fetchall()
        if not data:
            logger.info("No chats need to be terminated")
            return
        chat_ids, budget_ids, event_ids, schedule_ids, task_ids = zip(*data)
        self.core_session.execute(update(Chat).where(Chat.chat_id.in_(set(chat_ids))).values(state=State.TERMINATED))
        self.core_session.execute(delete(Budget).where(Budget.budget_id.in_(set(budget_ids))))
        self.core_session.execute(delete(Event).where(Event.event_id.in_(set(event_ids))))
        self.core_session.execute(delete(CrontabSchedule).where(CrontabSchedule.id.in_(schedule_ids)))
        self.core_session.execute(delete(PeriodicTask).where(PeriodicTask.id.in_(task_ids)))

        try:
            self.core_session.commit()
            self.schedule_session.commit()
            logger.info(f"Successfully terminated. Chats' state set to {State.TERMINATED}. Related db records deleted")
        except DatabaseError as e:
            logger.error(f"Failed to commit changes. Exception:\n{e}")
            self.core_session.rollback()
            self.schedule_session.rollback()

    def get_message(self, section: str, alias: str) -> Message:
        try:
            message = self.core_session.get(Message, (section, alias)).value
        except AttributeError as e:
            logger.error(f"Couldn't load message {section=}, {alias=}.\nException: {e}")
            message = config.CRITICAL_ERROR_MSG
        return message

    def upsert_message(self, section, alias, value):
        new_message = Message(section=section, alias=alias, value=value)
        self.core_session.merge(new_message)
        self.core_session.commit()


service_keeper = ServiceKeeper()
