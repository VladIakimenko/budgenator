from __future__ import annotations

import logging
import traceback
from random import randrange
from typing import Any, Callable, Optional

import telebot  # noqa

# Project
from core.models import EventType, DayOfTheWeek, ScheduleBasis
from telegram.bot import Bot, CurrentHandler
from telegram.utils import config_finished

logger = logging.getLogger(__name__)


class MockChat:
    """Mock Chat, used within the MockMessage only"""
    def __init__(self, id: int):
        self.id = id


class MockMessage:
    """A dummy message to be used instead of a real Message from pytelegrambotapi"""
    def __init__(self, chat: MockChat, text: str = ""):
        self.chat = chat
        self.text = text


class MockCall:
    """
    A helper class used solely to preserve the structure of the mockers methods,
    that imitate the work of the Bots methods, that expect the pytelegrambotapi's Call objects
    """
    def __init__(self, message: MockMessage, data: str):
        self.message = message
        self.data = data


class MockTeleBot(telebot.TeleBot):
    """
    Dummy class for mocking the telebot from pytelegrambotapi.
    Inherits from the original TeleBot for the typing purposes only.
    Fully overrides relevant methods with mock implementation.
    """

    def __init__(self): # noqa
        pass

    def send_message(self, *args, chat_id: int, text: str, **kwargs):
        print(text)


class Mocker(Bot):
    """
    The mock messenger inherits the handler-methods from the Bot,
    and is designed to test the rest of the app in isolation from telegram
    """

    def __init__(self):         # noqa
        self.chat_id = randrange(1, 100000)
        self.telebot = MockTeleBot()
        self.handler_triggers = {
            CurrentHandler.EVENT_TYPE: self.config_event_type,
            CurrentHandler.BASIS: self.config_basis,
            CurrentHandler.DAY_OF_THE_WEEK: self.config_day_of_the_week,
            CurrentHandler.DAY_OF_THE_MONTH: self.config_day_of_the_month,
            CurrentHandler.TIME: self.config_time,
        }

    def _mock_message(self, text: str = "") -> MockMessage:
        chat = MockChat(id=self.chat_id)
        message = MockMessage(chat=chat, text=text)
        return message

    def _mock_call(self, data: Any) -> MockCall:
        chat = MockChat(id=self.chat_id)
        message = MockMessage(chat=chat)
        call = MockCall(message=message, data=data)
        return call

    def start(self, user_input):
        if user_input == "start":
            self.handle_first_contact(self._mock_message())
            print("[Mocker] Use 'T', 'A', 'R', to config a new event type, 'done' to finish config")

    def config_event_type(self, user_input):
        data = {
            "t": EventType.REPLENISHMENT,
            "a": EventType.ANNULMENT,
            "r": EventType.REMINDER,
            "done": config_finished,
        }.get(user_input, user_input)
        self.handle_config_event_type(self._mock_call(data=data))

    def config_basis(self, user_input):
        data = {
            "d": ScheduleBasis.DAILY,
            "w": ScheduleBasis.DAY_OF_THE_WEEK,
            "m": ScheduleBasis.DAY_OF_THE_MONTH,
        }.get(user_input, user_input)
        self.handle_config_basis(self._mock_call(data=data))
        if data == ScheduleBasis.DAY_OF_THE_WEEK:
            print("[Mocker] Use one of: 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'")

    def config_day_of_the_week(self, user_input):
        data = {
            "mon": DayOfTheWeek.MONDAY,
            "tue": DayOfTheWeek.TUESDAY,
            "wed": DayOfTheWeek.WEDNESDAY,
            "thu": DayOfTheWeek.MONDAY,
            "fri": DayOfTheWeek.TUESDAY,
            "sat": DayOfTheWeek.WEDNESDAY,
            "sun": DayOfTheWeek.WEDNESDAY,
        }.get(user_input, user_input)
        self.handle_config_day_of_the_week(self._mock_call(data=data))

    def config_day_of_the_month(self, user_input):
        self.handle_config_day_of_the_month(self._mock_message(text=user_input))

    def config_time(self, user_input):
        self.handle_config_time(self._mock_message(text=user_input))

    def listen_and_process(self):
        """
        Mocker's listen_and_process method imitates the work of the Bot's listen_and_process method.
        It listens to user input in a loop, like the bot is listening to events or messages.
        """
        print("[Mocker] Telegram Mocker is running. Type anything to sim the first contact. Type 'exit' to quit.")
        while True:
            try:
                command = input("[Mocker] Enter command: ").casefold().strip()
                if command == 'exit':
                    break
                current_handler: CurrentHandler = self.current_handlers.get(self.chat_id)
                handler_trigger: Optional[Callable] = self.handler_triggers.get(current_handler)
                (handler_trigger or self.start)(command)
            except Exception as e:
                print(f"[Mocker][Error] {type(e).__name__}: {e}")


