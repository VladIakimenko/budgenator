import logging
import random
from functools import partial

import telebot      # noqa

from core.models import EventType
from telegram.bot import Bot

logger = logging.getLogger(__name__)


class MockChat:
    """Mock Chat, used within the MockMessage only"""
    def __init__(self, id: int):
        self.id = id


class MockMessage:
    """A dummy message to be used instead of a real Message from pytelegrambotapi"""
    def __init__(self, chat: MockChat):
        self.chat = chat


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
        self.chat_id = random.randrange(1, 100000)
        self.handlers = {
            "start": self.start,
            "T": partial(self.config_event_type, event_type=EventType.REPLENISHMENT),
            "A": partial(self.config_event_type, event_type=EventType.ANNULMENT),
            "R": partial(self.config_event_type, event_type=EventType.REMINDER),
            "DONE": ...,
        }
        self.telebot = MockTeleBot()

    # purely mocker methods (used to work with console commands in the debug mode)
    def start(self):
        chat = MockChat(id=self.chat_id)
        message = MockMessage(chat=chat)
        self.handle_first_contact(message)
        print("[Mocker] Use 'T', 'A', 'R', 'DONE' to config a new event type.")

    def config_event_type(self, event_type):
        chat = MockChat(id=self.chat_id)
        message = MockMessage(chat=chat)
        call = MockCall(message=message, data=event_type)
        self.handle_config_event_type(call)

    def listen_and_process(self):

        """
        Mocker's listen_and_process method imitates the work of the Bot's listen_and_process method.
        It listens to commands in a loop, like the bot is listening to events or messages.
        """
        print("[Mocker] Telegram Mocker is running. Type 'start' to sim first contact. Type 'exit' to quit.")
        while True:
            command = input("[Mocker] Enter command: ").strip()
            if command == 'exit':
                break
            self.handlers.get(command, lambda: print("[Mocker] Command not found!"))()
