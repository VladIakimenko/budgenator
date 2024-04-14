import os
import logging
import logging.config as logging_config

import pytz
from sqlalchemy import create_engine

logging_config.fileConfig('logging.ini')
logger = logging.getLogger(__name__)


MAX_IDLE_DAYS = int(os.environ["MAX_IDLE_DAYS"])
TIMEZONE = os.environ["TIMEZONE"]
try:
    pytz.timezone(TIMEZONE)
except pytz.exceptions.UnknownTimeZoneError as e:
    logger.error(
        f"Incorrectly configured timezone. Must be one of {', '.join(pytz.all_timezones)}"
    )
    raise e

# TODO collect stings from separate values
BEAT_DB_CONN_STRING = os.environ["BEAT_DB_CONN_STRING"]
CORE_DB_CONN_STRING = os.environ["CORE_DB_CONN_STRING"]
BROKER_CONN_STRING = os.environ["BROKER_CONN_STRING"]
RESULT_BACKEND_CONN_STRING = os.environ["RESULT_BACKEND_CONN_STRING"]

core_engine = create_engine(url=CORE_DB_CONN_STRING)
schedule_engine = create_engine(url=BEAT_DB_CONN_STRING)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TEXT_FILEPATH = "text.ini"
CRITICAL_ERROR_MSG = "Critical Server Error occurred. Please come back later!"

DEBUG = os.environ.get("DEBUG", False)
