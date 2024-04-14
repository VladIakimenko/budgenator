import logging

import telebot  # noqa

from core.managers import ChatManager, service_keeper
from core.models import EventType, ScheduleEntry, ScheduleBasis, DayOfTheWeek
from core.utils import singleton
from telegram.configurator import CONFIG_MESSAGE_MAP, config_finished

logger = logging.getLogger(__name__)


@singleton
class Bot:
    managers = dict()
    configs = dict()

    def __init__(self, token):
        self.telebot = self.telebot = telebot.TeleBot(token)

    def listen_and_process(self):
        """
        This method initializes the bot's message handlers,
        representing its main loop, handling incoming messages and events.
        The decorators are used to associate each func with a trigger,
        that launches its execution.
        https://github.com/eternnoir/pyTelegramBotAPI?tab=readme-ov-file#message-handlers
        """

        @self.telebot.message_handler(commands=['start'])
        def first_contact(message):
            return self.handle_first_contact(message)

        @self.telebot.callback_query_handler(func=lambda call: True)
        def configure_event_type(call):
            return self.handle_config_event_type(call)

        @self.telebot.callback_query_handler(func=lambda call: True)
        def configure_basis(call):
            return self.handle_config_basis(call)

        @self.telebot.callback_query_handler(func=lambda call: True)
        def configure_time(call):
            return self.handle_config_time(call)

    def handle_first_contact(self, message):
        chat_id = message.chat.id

        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("first_contact", "welcome"),
        )
        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("first_contact", "overview"),
        )
        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("config", "intro"),
        )
        logger.info(f"First contact with {chat_id=}. Anticipating config.")
        self.send_config_menu(chat_id)

    def handle_config_event_type(self, call):
        """
        All the config methods together loop up from and to this method
        until the config_finished sentinel value is received.
        """
        chat_id = call.message.chat.id
        if call.data is config_finished:
            # TODO: check is fully configured, step out of the loop
            ...
        self.configs[chat_id] = ScheduleEntry(event_type=call.data)
        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message(*CONFIG_MESSAGE_MAP[call.data]),
        )
        self.request_config_basis(chat_id)

    def handle_config_basis(self, call):
        chat_id = call.message.chat.id
        basis = call.data   # type: ScheduleBasis
        self.configs[chat_id].basis = basis
        match basis:
            case ScheduleBasis.DAILY:
                self.request_config_time(chat_id)
            case ScheduleBasis.DAY_OF_THE_WEEK:
                self.request_config_day_of_the_week(chat_id)
            case ScheduleBasis.DAY_OF_THE_MONTH:
                self.request_config_day_of_the_month(chat_id)

    def handle_config_day_of_the_week(self, call):
        chat_id = call.message.chat.id
        self.configs[chat_id].day = call.data   # type: DayOfTheWeek
        self.request_config_time(chat_id)

    def handle_config_day_of_the_month(self, call):
        chat_id = call.message.chat.id
        self.configs[chat_id].day = call.data   # type: int
        self.request_config_time(chat_id)

    def handle_config_time(self, call):
        chat_id = call.message.chat.id
        self.configs[chat_id].time = call.data      # TODO: how to handle time?
        schedule_entry = ...                        # TODO: parse dict, create dto and db objs, clear dict
        self.send_config_menu(chat_id)

    def send_config_menu(self, chat_id):
        markup = telebot.types.InlineKeyboardMarkup()
        buttons = [
            ("T", EventType.REPLENISHMENT),
            ("A", EventType.ANNULMENT),
            ("R", EventType.REMINDER),
            ("DONE", config_finished),
        ]
        for button in buttons:
            markup.add(telebot.types.InlineKeyboardButton(button))

        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("config", "menu"),
            reply_markup=markup,
        )

    def request_config_basis(self, chat_id):
        markup = telebot.types.InlineKeyboardMarkup()
        buttons = [
            ("D", ScheduleBasis.DAILY),
            ("W", ScheduleBasis.DAY_OF_THE_WEEK),
            ("M", ScheduleBasis.DAY_OF_THE_MONTH),
        ]
        for button in buttons:
            markup.add(telebot.types.InlineKeyboardButton(button))

        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("config", "basis"),
            reply_markup=markup
        )

    def request_config_time(self, chat_id):
        ...
        # TODO:
        # implement menu for configuring time

    def request_config_day_of_the_week(self, chat_id):
        ...
        # TODO:
        # implement menu for configuring the day of the week

    def request_config_day_of_the_month(self, chat_id):
        ...
        # TODO:
        # implement menu for configuring the day of the month
