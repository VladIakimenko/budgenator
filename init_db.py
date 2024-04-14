import configparser
import logging
import logging.config as logging_config

from celery_sqlalchemy_scheduler.session import ModelBase as ScheduleBase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Project
import config
from core.models import Base as CoreBase, Message

logging_config.fileConfig('logging.ini')
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    try:
        logger.info("Initializing task_manager beat scheduling database...")
        engine = create_engine(url=config.BEAT_DB_CONN_STRING)
        ScheduleBase.metadata.create_all(bind=engine)
        logger.info("Tables successfully created")
    except Exception as e:
        logger.error(f"Celery Beat scheduling database initialization failed.\n{e}")

    try:
        logger.info("Initializing core database...")
        engine = create_engine(url=config.CORE_DB_CONN_STRING)
        CoreBase.metadata.create_all(bind=engine)
        logger.info("Tables successfully created")
        text_filepath = config.TEXT_FILEPATH
        logger.info(f"Filling the Core database with messages from {text_filepath}...")
        session = sessionmaker(bind=engine)()
        parser = configparser.ConfigParser()
        parser.read(text_filepath)
        for section in parser.sections():
            for option in parser.options(section):
                message = Message(section=section, alias=option, value=parser.get(section, option))
                session.add(message)
                logger.info(f"Message db object created. {section=}, alias='{option}'")
        session.commit()
    except Exception as e:
        logger.error(f"Core database initialization failed.\n{e}")
