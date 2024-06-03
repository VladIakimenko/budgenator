from __future__ import annotations

import logging
from enum import Enum
from decimal import Decimal
from datetime import datetime

import telebot  # noqa

# Project
from core.models import State, EventType, DayOfTheWeek, ScheduleBasis, ScheduleEntry
from core.managers import ChatManager, service_keeper
from telegram.utils import config_finished

logger = logging.getLogger(__name__)


class CurrentHandler(Enum):
    EVENT_TYPE = "EVENT_TYPE"
    BASIS = "BASIS"
    DAY_OF_THE_WEEK = "DAY_OF_THE_WEEK"
    DAY_OF_THE_MONTH = "DAY_OF_THE_MONTH"
    TIME = "TIME"
    ON_DUTY = "ON_DUTY"


class Bot:
    managers: dict[int, ChatManager] = {}
    configs: dict[int, ScheduleEntry] = {}
    current_handlers: dict[int: CurrentHandler] = {}

    def __init__(self, token):
        self.telebot = telebot.TeleBot(token)

        self.text_handlers_map = {
            CurrentHandler.ON_DUTY: self.handle_message,
            CurrentHandler.DAY_OF_THE_MONTH: self.handle_config_day_of_the_month,
            CurrentHandler.TIME: self.handle_config_time,
        }

        self.button_handlers_map = {
            CurrentHandler.EVENT_TYPE: self.handle_config_event_type,
            CurrentHandler.BASIS: self.handle_config_basis,
            CurrentHandler.DAY_OF_THE_WEEK: self.handle_config_day_of_the_week,
        }

    def listen_and_process(self):
        """
        This method initializes the bot's message handlers,
        representing its main loop, it listens to incoming messages and events.
        The decorators are used to associate each func with a trigger,
        that launches its execution.
        https://github.com/eternnoir/pyTelegramBotAPI?tab=readme-ov-file#message-handlers
        """

        @self.telebot.message_handler(commands=['start'])
        def first_contact(message):
            self.handle_first_contact(message)

        @self.telebot.message_handler(content_types=['text'])
        def handle_text(message) -> None:
            current_handler: CurrentHandler = self.current_handlers[message.chat.id]
            self.text_handlers_map[current_handler](message)        # TODO

        @self.telebot.callback_query_handler(func=lambda call: True)
        def configure(call):
            current_handler: CurrentHandler = self.current_handlers[call.message.chat.id]
            self.button_handlers_map[current_handler](call)         # TODO

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
        self.current_handlers[chat_id] = CurrentHandler.EVENT_TYPE

    def handle_config_event_type(self, call):
        """
        All the config methods together loop up from and to this method
        until the config_finished sentinel value is received.
        """
        chat_id = call.message.chat.id

        if call.data is config_finished:
            state = self.managers[chat_id].get_state()
            match state:
                case State.INITIAL:
                    self.telebot.send_message(
                        chat_id=chat_id,
                        text=service_keeper.get_message("config", "not_configured"),
                    )
                    self.current_handlers[chat_id] = CurrentHandler.EVENT_TYPE
                    self.send_config_menu(chat_id)
                case State.TERMINATED:
                    self.telebot.send_message(
                        chat_id=chat_id,
                        text=service_keeper.get_message("config", "not_configured"),
                    )
                case State.CONFIGURED:
                    self.telebot.send_message(
                        chat_id=chat_id,
                        text=service_keeper.get_message("config", "success"),
                    )
                    self.current_handlers[chat_id] = CurrentHandler.ON_DUTY
                    logger.info(
                        f"The configuration of the chat with {chat_id=} has been finished. "
                        f"Switched to {CurrentHandler.ON_DUTY.value} handler."
                    )
                    return

        self.configs[chat_id] = ScheduleEntry(event_type=call.data)
        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message(
                *{
                    EventType.REPLENISHMENT: ("config", "replenishment"),
                    EventType.ANNULMENT: ("config", "annulment"),
                    EventType.REMINDER: ("config", "reminder"),
                }[call.data]
            ),
        )
        self.current_handlers[chat_id] = CurrentHandler.BASIS
        self.request_config_basis(chat_id)

    def handle_config_basis(self, call):
        chat_id = call.message.chat.id
        basis = call.data   # type: ScheduleBasis
        self.configs[chat_id].basis = basis
        match basis:
            case ScheduleBasis.DAILY:
                self.current_handlers[chat_id] = CurrentHandler.TIME
                self.request_config_time(chat_id)
            case ScheduleBasis.DAY_OF_THE_WEEK:
                self.current_handlers[chat_id] = CurrentHandler.DAY_OF_THE_WEEK
                self.request_config_day_of_the_week(chat_id)
            case ScheduleBasis.DAY_OF_THE_MONTH:
                self.current_handlers[chat_id] = CurrentHandler.DAY_OF_THE_MONTH
                self.request_config_day_of_the_month(chat_id)

    def handle_config_day_of_the_week(self, call):
        chat_id = call.message.chat.id
        self.configs[chat_id].day = call.data   # type: DayOfTheWeek
        self.current_handlers[chat_id] = CurrentHandler.TIME
        self.request_config_time(chat_id)

    def handle_config_day_of_the_month(self, message):
        chat_id = message.chat.id
        try:
            day = int(message.text)
            assert 1 <= day <= 31
            self.configs[chat_id].day = day
            self.current_handlers[chat_id] = CurrentHandler.TIME
            self.request_config_time(chat_id)
        except (ValueError, AssertionError):
            self.request_config_day_of_the_month(chat_id, repeated=True)

    def handle_config_time(self, message):
        chat_id = message.chat.id
        time_str = message.text
        try:
            self.configs[chat_id].time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            self.request_config_time(chat_id, repeated=True)

        chat_manager = self.managers.get(chat_id)
        if chat_manager is None:
            chat_manager = ChatManager(chat_id=chat_id)
            chat_manager.engage(Decimal(1000), Decimal(1000))
            self.managers[chat_id] = chat_manager
        schedule_entry = self.configs.pop(chat_id)
        chat_manager.scheduler.schedule_crontab_task(record=schedule_entry)
        chat_manager.refresh_latest_contact()
        if schedule_entry.event_type == EventType.REPLENISHMENT:
            chat_manager.set_configured()
        elif schedule_entry.event_type == EventType.REMINDER:
            chat_manager.engage_reminder()
        self.send_config_menu(chat_id)
        self.current_handlers[chat_id] = CurrentHandler.EVENT_TYPE

    def handle_message(self, message):
        # TODO set chat's reminder_silenced to True
        # TODO refresh_latest_contact for the Chat
        ...

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

    def request_config_day_of_the_week(self, chat_id):
        markup = telebot.types.InlineKeyboardMarkup()
        buttons = [
            ("MON", DayOfTheWeek.MONDAY),
            ("TUE", DayOfTheWeek.TUESDAY),
            ("WED", DayOfTheWeek.WEDNESDAY),
            ("THU", DayOfTheWeek.THURSDAY),
            ("FRI", DayOfTheWeek.FRIDAY),
            ("SAT", DayOfTheWeek.SATURDAY),
            ("SUN", DayOfTheWeek.SUNDAY),
        ]
        for button in buttons:
            markup.add(telebot.types.InlineKeyboardButton(button))

        self.telebot.send_message(
            chat_id=chat_id,
            text=service_keeper.get_message("config", "day_of_the_week"),
            reply_markup=markup
        )

    def request_config_day_of_the_month(self, chat_id, repeated=False):
        self.telebot.send_message(
            chat_id=chat_id,
            text=(
                service_keeper.get_message("config", "day_of_the_month_wrong_input")
                if repeated
                else service_keeper.get_message("config", "day_of_the_month")
            ),
        )

    def request_config_time(self, chat_id, repeated=False):
        self.telebot.send_message(
            chat_id=chat_id,
            text=(
                service_keeper.get_message("config", "time_wrong_input")
                if repeated
                else service_keeper.get_message("config", "time")
            ),
        )


