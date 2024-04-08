import logging

from sqlalchemy import create_engine
from celery_sqlalchemy_scheduler.session import ModelBase as ScheduleBase

import config
from core.models import Base as CoreBase


logger = logging.getLogger("init")


def init_db(conn_string, base):
    engine = create_engine(url=conn_string)
    base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    try:
        logger.info("Initializing celery beat scheduling database...")
        init_db(config.BEAT_DB_CONN_STRING, ScheduleBase)
        logger.info("Tables successfully created")
    except Exception as e:
        logger.error(f"Celery Beat scheduling database initialization failed.\n{e}")

    try:
        logger.info("Initializing core database...")
        init_db(config.CORE_DB_CONN_STRING, CoreBase)
        logger.info("Tables successfully created")
    except Exception as e:
        logger.error(f"Core database initialization failed.\n{e}")
    # init_db(config.CORE_DB_CONN_STRING, CoreBase)
