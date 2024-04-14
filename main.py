import config
from telegram.bot import Bot
from telegram.mocker import Mocker

telegram_bot = Mocker() if config.DEBUG else Bot(token=config.TELEGRAM_BOT_TOKEN)

if __name__ == '__main__':
    telegram_bot.listen_and_process()
