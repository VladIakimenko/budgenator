import time
import logging
import configparser
from datetime import datetime, timedelta

# Project
import config
from core.managers import ChatManager, service_keeper

from . import celery_app

__all__ = [
    "terminate_idle_task",
    "reload_messages_task",
    "send_reminder_task",
    "refill_balance_task",
    "annul_balance_task",
]

logger = logging.getLogger(__name__)


@celery_app.task
def terminate_idle_task():
    """
    Find chats that have been idle for too long.
    Set the state to "TERMINATED" for every outdated chat.
    Clear other related records from schedule and core databases.
    """
    logger.info("Starting terminate_idle_task...")
    time_start = time.time()
    message_counter = 0
    chat_ids, schedule_ids, task_ids = service_keeper.collect_ids_for_termination()
    if chat_ids:
        service_keeper.butch_terminate(chat_ids)
    if any([schedule_ids, task_ids]):
        service_keeper.butch_delete(schedule_ids, task_ids)
    logger.info(
        f"Finished executing terminate_idle_task. "
        f"{message_counter} messages processed during {time.time() - time_start} seconds."
    )


@celery_app.task
def reload_messages_task():
    """
    Reloads messages from the file.
    Used for updating the bots messages without restarting the app.
    """
    logger.info("Starting reload_messages_task...")
    time_start = time.time()
    message_counter = 0
    parser = configparser.ConfigParser()
    parser.read(config.TEXT_FILEPATH)
    for section in parser.sections():
        for option in parser.options(section):
            service_keeper.upsert_message(section, option, parser.get(section, option))
            message_counter += 1
    logger.info(
        f"Finished executing reload_messages_task. "
        f"{message_counter} messages processed during {time.time() - time_start} seconds."
    )


@celery_app.task
def send_reminder_task(chat_id: int):
    manager = ChatManager(chat_id)
    if not manager.reminder_silenced:
        ...
        # TODO send reminder...
    logger.info(f"Reminder sent to {chat_id=}")


@celery_app.task
def refill_balance_task(chat_id: int):
    manager = ChatManager(chat_id)
    manager.top_up()
    manager.reset_reminder()
    logger.info(f"Balance refilled for {chat_id=}")


@celery_app.task
def annul_balance_task(chat_id: int):
    manager = ChatManager(chat_id)
    manager.annul()
    logger.info(f"The balance has been reset for {chat_id=}")
