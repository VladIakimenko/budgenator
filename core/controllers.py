import logging
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

import config
from core.models import Budget

logger = logging.getLogger(__name__)

core_engine = create_engine(url=config.CORE_DB_CONN_STRING)
schedule_engine = create_engine(url=config.BEAT_DB_CONN_STRING)


class BudgetController:
    def __init__(self):
        self.db_session: Session = sessionmaker(bind=core_engine)()
    ...

    def get_balance(self, chat_id: uuid.UUID):
        return self.db_session.execute(
            select(Budget.balance)
            .where(Budget.chat_id == chat_id)
        ).scalar()

    # TODO
    # def spend
    # def top_up
    # def annul
    # def change_replenishment


class ScheduleController:

    def __init__(self):
        self.db_session: Session = sessionmaker(bind=schedule_engine)()



    ...
    # TODO Implement the methods that would create relevant models in the schedule database


# TODO instantiate controllers to global context
