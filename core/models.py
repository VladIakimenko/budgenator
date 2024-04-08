import uuid
import enum
import datetime
import decimal
from typing import Annotated

from sqlalchemy import Numeric, text, ForeignKey
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from celery_sqlalchemy_scheduler.models import PeriodicTask, CrontabSchedule


__all__ = [
    "Base",
    "Chat",
    "Budget",
    "DayOfTheWeek",
    "ScheduleBasis",
    "PeriodicTask",
    "CrontabSchedule",
]


Base = declarative_base()


# scheduling
class DayOfTheWeek(str, enum.Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY", True
    SUNDAY = "SUNDAY", True

    def __new__(cls, value, is_weekend: bool = False):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.is_weekend = is_weekend
        return obj


class ScheduleBasis(str, enum.Enum):
    DAILY = "DAILY"
    DAY_OF_THE_MONTH = "DAY_OF_THE_MONTH"
    DAY_OF_THE_WEEK = "DAY_OF_THE_WEEK"


class ScheduleEntryDto:
    def __init__(
            self,
            basis: ScheduleBasis,
            time: datetime.time = datetime.time(0, 0),
            day: DayOfTheWeek | str | int = None
    ):
        self.basis = basis
        self.time = time
        if day is not None:
            self.day = day
            self._validate_day()

    def _validate_day(self):
        match self.basis:

            case ScheduleBasis.DAILY:
                raise AttributeError(f"The 'day' attribute is not applicable for the {ScheduleBasis.DAILY.value} basis")

            case ScheduleBasis.DAY_OF_THE_MONTH:
                if not isinstance(self.day, int) or not 1 <= self.day <= 31:
                    raise AttributeError(f"The 'day' must be an int, between 1 and 31")

            case ScheduleBasis.DAY_OF_THE_WEEK:
                try:
                    DayOfTheWeek(self.day)
                except ValueError as e:
                    raise AttributeError(f"The 'day' value must be one of {', '.join(DayOfTheWeek)}") from e


# budgeting
class State(str, enum.Enum):
    INITIAL = "INITIAL"
    CONFIGURED = "CONFIGURED"
    TERMINATED = "TERMINATED"


class Chat(Base):
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[State] = mapped_column(default=State.INITIAL, server_default=State.INITIAL.value)
    created_at: Mapped[datetime.datetime]
    latest_msg_received_at: Mapped[datetime.datetime]


money = Annotated[
    decimal.Decimal,
    mapped_column(
        Numeric(precision=10, scale=2),
        default=0.00,
        server_default=text("0.00")
    ),
]


class Budget(Base):
    budget_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # We assign budgets to chats, rather than users, to allow using one budget in group chat
    chat_id: Mapped[int] = mapped_column(ForeignKey(Chat.chat_id))
    balance: Mapped[money]
    replenishment: Mapped[money]
