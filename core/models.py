import enum
import uuid
import decimal
import datetime
from typing import Annotated

from sqlalchemy import Numeric, ForeignKey, text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, declarative_base

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
class DayOfTheWeek(str, enum.Enum):
    MONDAY = "MONDAY", 1, False
    TUESDAY = "TUESDAY", 2, False
    WEDNESDAY = "WEDNESDAY", 3, False
    THURSDAY = "THURSDAY", 4, False
    FRIDAY = "FRIDAY", 5, False
    SATURDAY = "SATURDAY", 6, True
    SUNDAY = "SUNDAY", 7, True

    def __new__(cls, value, ordinal_number: int, is_weekend: bool = False):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.ordinal_number = ordinal_number
        obj.is_weekend = is_weekend
        return obj


class ScheduleBasis(str, enum.Enum):
    DAILY = "DAILY"
    DAY_OF_THE_WEEK = "DAY_OF_THE_WEEK"
    DAY_OF_THE_MONTH = "DAY_OF_THE_MONTH"


class EventType(str, enum.Enum):
    REPLENISHMENT = "REPLENISHMENT", "task_manager.tasks.refill_balance", True
    ANNULMENT = "ANNULMENT", "task_manager.tasks.annul_balance", True
    REMINDER = "REMINDER", "task_manager.tasks.send_reminder", True
    IDLE_CHATS_TERMINATION = "IDLE_CHATS_TERMINATION", "task_manager.tasks.terminate_idle"

    def __new__(
        cls,
        value,
        task: str,
        requires_chat_id: bool = False,
    ):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.task = task
        obj.requires_chat_id = requires_chat_id
        return obj


class State(str, enum.Enum):
    INITIAL = "INITIAL"
    CONFIGURED = "CONFIGURED"
    TERMINATED = "TERMINATED"


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
    schedule_ids: Mapped[list] = mapped_column(JSON, default=[], server_default=text("[]"))
    task_ids: Mapped[list] = mapped_column(JSON, default=[], server_default=text("[]"))


money = Annotated[
    decimal.Decimal,
    mapped_column(
        Numeric(precision=10, scale=2), default=0.00, server_default=text("0.00")
    ),
]


class Budget(Base):
    __tablename__ = "budget"
    budget_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4(),
        server_default=func.gen_random_uuid(),
    )
    # We assign budgets to chats, rather than users, to allow using one budget in a group chat
    chat_id: Mapped[int] = mapped_column(ForeignKey(Chat.chat_id))
    balance: Mapped[money]
    replenishment: Mapped[money]


class Message(Base):
    __tablename__ = "message"
    section: Mapped[str] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(default="", server_default='')