# Project
import config
from telegram.bot import Bot
from telegram.mocker import Mocker

telegram_bot = Mocker() if config.DEBUG else Bot(token=config.TELEGRAM_BOT_TOKEN)

if __name__ == '__main__':
    telegram_bot.listen_and_process()

# TODO:
# 1) desgin the message handler for on_duty
# 2) create the beat instruction to run load the messages task daily (make configurable)
# 3) keep on with the reminder task. There probably will be only one reminder available, since the property belongs to the Chat
# 4) keep on with the annulment

