import os
import logging
import pytz

logger = logging.getLogger("init")


TIMEZONE = os.environ["TIMEZONE"]
try:
    pytz.timezone(TIMEZONE)
except pytz.exceptions.UnknownTimeZoneError as e:
    logger.error(f"Incorrectly configured timezone. Must be one of {', '.join(pytz.all_timezones)}")
    raise e

# TODO collect stings from separate values
BEAT_DB_CONN_STRING = os.environ["BEAT_DB_CONN_STRING"]
CORE_DB_CONN_STRING = os.environ["CORE_DB_CONN_STRING"]
BROKER_CONN_STRING = os.environ["BROKER_CONN_STRING"]
RESULT_BACKEND_CONN_STRING = os.environ["RESULT_BACKEND_CONN_STRING"]

