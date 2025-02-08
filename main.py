import logging
import sys
import asyncio
from aiogram.client.bot import Bot, DefaultBotProperties
from aiogram import Dispatcher
from utils.storage import check_or_create_token_file, load_token
from handlers.start import register_start_handlers
from handlers.add_kasa import register_add_kasa_handlers
from handlers.general_commands import register_general_commands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    check_or_create_token_file()
    tg_token = load_token()
    bot = Bot(token=tg_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    register_start_handlers(dp, bot)
    register_add_kasa_handlers(dp)
    register_general_commands(dp)

    async def runner():
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    try:
        asyncio.run(runner())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот зупинений")

if __name__ == "__main__":
    main()