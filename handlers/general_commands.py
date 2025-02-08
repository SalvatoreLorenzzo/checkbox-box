import logging
from aiogram import types
from aiogram.filters import Command
from aiogram import Dispatcher

logger = logging.getLogger(__name__)

async def cmd_help(message: types.Message):
    text = (
        "Список команд:\n"
        "/start - Перевірити статус кас\n"
        "/add_kasa - Додати касу\n"
        "/list_kasas - Переглянути всі каси\n"
        "/help - Допомога (це повідомлення)"
    )
    await message.answer(text)

def register_general_commands(dp: Dispatcher):
    dp.message.register(cmd_help, Command('help'))