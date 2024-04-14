import logging

import telebot    # noqa

from core.models import EventType
from core.utils import singleton

logger = logging.getLogger(__name__)

CONFIG_MESSAGE_MAP = {
    EventType.REPLENISHMENT: ("config", "replenishment"),
    EventType.ANNULMENT: ("config", "annulment"),
    EventType.REMINDER: ("config", "reminder"),
}


@singleton
class ConfigFinishedSignal:
    """A sentinel class to pass a signal, that the user intends to mark config finished"""
    pass


config_finished = ConfigFinishedSignal()


#
# class Configurator:
#     message_map = {
#         EventType.REPLENISHMENT: ("config", "replenishment"),
#         EventType.ANNULMENT: ("config", "annulment"),
#         EventType.REMINDER: ("config", "reminder"),
#     }
#
#     def __init__(self, telebot_instance: telebot.TeleBot):
#         self.telebot_instance = telebot_instance
#         self.basis = None
#         self.time = None
#         self.day = None
#
#
#     def request_basis(self):
#
#         # define markup
#         markup = telebot.types.ReplyKeyboardMarkup(row_width=1)
#         for letter in "DWM":
#             button = telebot.types.KeyboardButton(letter)
#             markup.add(button)
#
#         # send message
#         self.telebot_instance.send_message(
#             self.chat_id,
#             service_keeper.get_message("config", "basis"),
#             reply_markup=markup
#         )
#
#     def handle_basis(self, message):
#         self.basis = ScheduleBasis[message.text]
#         self.ask_for_time()
#
#     def ask_for_time(self):
#         # Here you would implement the logic to ask for the time
#         # For simplicity, let's assume the time is set to a fixed value
#         self.time = datetime.time(12, 0) # Example time
#         self.state = 'day'
#         self.ask_for_day()
#
#     def ask_for_day(self):
#         if self.basis == ScheduleBasis.DAILY:
#             # For Basis.DAILY, no need to ask for the day
#             self.finalize_configuration()
#         else:
#             # For other bases, ask for the day
#             markup = types.ReplyKeyboardMarkup(row_width=1)
#             if self.basis == ScheduleBasis.DAY_OF_THE_MONTH:
#                 for day in range(1, 32): # Assuming 31 days in a month for simplicity
#                     button = types.KeyboardButton(str(day))
#                     markup.add(button)
#             elif self.basis == ScheduleBasis.DAY_OF_THE_WEEK:
#                 for day in DayOfTheWeek:
#                     button = types.KeyboardButton(day)
#                     markup.add(button)
#             bot.send_message(self.chat_id, "Please choose the day:", reply_markup=markup)
#             self.state = 'day_selected'
#
#     def handle_day(self, message):
#         # Here you would handle the user's day selection
#         # For simplicity, let's assume the day is set to a fixed value
#         self.day = message.text
#         self.finalize_configuration()
#
#     def finalize_configuration(self):
#         # Here you would finalize the configuration and store it as needed
#         # For example, creating a ScheduleEntry instance
#         entry = ScheduleEntry(self.event_type, self.basis, self.time, self.day)
#         bot.send_message(self.chat_id, f"Configuration finalized: {entry}")
#         self.state = None # Reset the state