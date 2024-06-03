from __future__ import annotations

import datetime
from enum import Enum
from uuid import UUID, uuid4
from typing import Annotated
from decimal import Decimal

from sqlalchemy import UUID as UUIDType
from sqlalchemy import Integer, Numeric, ForeignKey, func, text
from sqlalchemy.orm import (Mapped,
                            relationship,
                            declared_attr,
                            mapped_column,
                            declarative_base,)
from sqlalchemy.ext.declarative import AbstractConcreteBase
from celery_sqlalchemy_scheduler.models import PeriodicTask, CrontabSchedule

__all__ = [
    "Base",
    "State",
    "ScheduleBasis",
    "DayOfTheWeek",
    "EventType",
    "ScheduleEntry",
    "Chat",
    "Budget",
    "Message",
    "PeriodicTask",
    "CrontabSchedule",
]

Base = declarative_base()


# enum
class DayOfTheWeek(Enum):
    MONDAY = "MONDAY", 1, False
    TUESDAY = "TUESDAY", 2, False
    WEDNESDAY = "WEDNESDAY", 3, False
    THURSDAY = "THURSDAY", 4, False
    FRIDAY = "FRIDAY", 5, False
    SATURDAY = "SATURDAY", 6, True
    SUNDAY = "SUNDAY", 7, True

    def __new__(cls, value, ordinal_number: int, is_weekend: bool = False):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.ordinal_number = ordinal_number
        obj.is_weekend = is_weekend
        return obj


class ScheduleBasis(Enum):
    DAILY = "DAILY"
    DAY_OF_THE_WEEK = "DAY_OF_THE_WEEK"
    DAY_OF_THE_MONTH = "DAY_OF_THE_MONTH"


class EventType(Enum):
    REPLENISHMENT = "REPLENISHMENT", "task_manager.celery_config.refill_balance_task", True
    ANNULMENT = "ANNULMENT", "task_manager.celery_config.annul_balance_task", True
    REMINDER = "REMINDER", "task_manager.celery_config.send_reminder_task", True

    def __new__(
        cls,
        value,
        task: str,
        model: Base,
        requires_chat_id: bool = False,
    ):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.task = task
        obj.model = model
        obj.requires_chat_id = requires_chat_id
        return obj


class State(Enum):
    INITIAL = "INITIAL"
    CONFIGURED = "CONFIGURED"
    TERMINATED = "TERMINATED"


class AnnulmentCondition(Enum):
    ...
    # TODO


# dto
class ScheduleEntry:
    def __init__(
        self,
        event_type: EventType,
        basis: ScheduleBasis = None,
        time: datetime.time = None,
        day: DayOfTheWeek | str | int = None,
    ):
        self.event_type = event_type
        self.basis = basis
        self.time = time
        self._day = day

    @property
    def day(self):
        return self._day

    @day.setter
    def day(self, value):
        self._day = value
        if value is not None:
            self._validate_day()

    def _validate_day(self):
        match self.basis:

            case ScheduleBasis.DAILY:
                raise AttributeError(
                    f"The 'day' attribute is not applicable for the {ScheduleBasis.DAILY.value} basis"
                )

            case ScheduleBasis.DAY_OF_THE_MONTH:
                if not isinstance(self.day, int) or not 1 <= self.day <= 31:
                    raise AttributeError(f"The 'day' must be an int, between 1 and 31")

            case ScheduleBasis.DAY_OF_THE_WEEK:
                try:
                    DayOfTheWeek(self.day)
                except ValueError as e:
                    raise AttributeError(
                        f"The 'day' value must be one of {', '.join(DayOfTheWeek)}"
                    ) from e


# orm
class Chat(Base):
    __tablename__ = "chat"
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[State] = mapped_column(
        default=State.INITIAL, server_default=State.INITIAL.value
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    latest_contact: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # relations
    budget: Mapped[Budget] = relationship(back_populates="chat")
    events: Mapped[list[Event]] = relationship(back_populates="chat")


money = Annotated[
    Decimal,
    mapped_column(
        Numeric(precision=10, scale=2), default=0.00, server_default=text("0.00")
    ),
]


class Budget(Base):
    __tablename__ = "budget"
    budget_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4(),
        server_default=func.gen_random_uuid(),
    )
    # We assign budgets to chats, rather than users, to allow using one budget in a group chat
    chat_id: Mapped[int] = mapped_column(
        ForeignKey(Chat.chat_id, onupdate="CASCADE", ondelete="CASCADE"))
    balance: Mapped[money]

    # relations
    chat: Mapped[Chat] = relationship(back_populates="budget")


class Event(AbstractConcreteBase, Base):
    strict_attrs = True

    @declared_attr
    def event_id(cls):
        return mapped_column(
            UUIDType,
            primary_key=True,
            default=uuid4(),
            server_default=func.gen_random_uuid(),
        )

    @declared_attr
    def chat_id(cls):
        return mapped_column(
            Integer,
            ForeignKey(Chat.chat_id, onupdate="CASCADE", ondelete="CASCADE"),
            nullable=False,
        )

    @declared_attr
    def schedule_id(cls):
        return mapped_column(Integer, nullable=False)

    @declared_attr
    def task_id(cls):
        return mapped_column(Integer, nullable=False)

    # relations
    @declared_attr
    def chat(cls):
        return relationship(Chat, back_populates="events")


class ReplenishmentEvent(Event):
    __tablename__ = 'replenishment'
    size: Mapped[money]

    __mapper_args__ = {
        'polymorphic_identity': EventType.REPLENISHMENT.value,
        'concrete':True
    }


class ReminderEvent(Event):
    __tablename__ = 'reminder'
    silenced: Mapped[bool] = mapped_column(default=False, server_default="FALSE")

    __mapper_args__ = {
        'polymorphic_identity': EventType.REMINDER.value,
        'concrete': True
    }


class AnnulmentEvent(Event):
    __tablename__ = 'annulment'
    condition: Mapped[AnnulmentCondition | None] = mapped_column(default=None, server_default="NULL")

    __mapper_args__ = {
        'polymorphic_identity': EventType.ANNULMENT.value,
        'concrete': True
    }


class Message(Base):
    __tablename__ = "message"
    section: Mapped[str] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(default="", server_default='')