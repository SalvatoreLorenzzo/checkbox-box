import logging
import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from utils.storage import check_or_create_token_file, load_token
from handlers.start import register_start_handlers
from handlers.add_kasa import register_add_kasa_handlers
from handlers.general_commands import register_general_commands
from utils.log_config import setup_logging

# Ініціалізуємо логування
setup_logging()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    check_or_create_token_file()
    bot = Bot(
        token=load_token(),
        default=DefaultBotProperties(parse_mode="HTML")
    )
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
    except Exception as e:
        logger.critical(f"Критична помилка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
Чеки вывода средств выводятся, хоть условия не позволяют (service_out != 0). Всё остальное работает. Вывод чеков актуальной смены пока что оставляю. 
Так же, проблема в звіте, неправильно подтягиваются чеки. Должны подтягиваться все за смену, но подтягивается только последний.
Следующие действия:
* ++ Исправить проблему чеков вывода. Добавить обработку чеков ввода.
* Добавить вывод X/Z отчётов
* Проверить, всё ли работает
* Сделать интерфейс для удобной работы.
* Найти хостинг и настроить
"""
