import logging
from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StateFilter
from datetime import datetime, timezone
from services.checkbox_api import get_cashier_token, get_kasa_name
from utils.storage import save_kasas_data
from handlers.start import kasas_data, get_shift_status_msg, start_background_polling

logger = logging.getLogger(__name__)

class AddKasaStates(StatesGroup):
    waiting_for_license_key = State()
    waiting_for_pin_code = State()

async def cmd_add_kasa(message: types.Message, state: FSMContext):
    await message.answer("Введіть ключ ліцензії каси (X-License-Key):")
    await state.set_state(AddKasaStates.waiting_for_license_key)

async def process_license_key(message: types.Message, state: FSMContext):
    license_txt = message.text.strip()
    await state.update_data(license_key=license_txt)
    await message.answer("Введіть PIN-код касира:")
    await state.set_state(AddKasaStates.waiting_for_pin_code)

async def process_pin_code(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    lic = data.get('license_key')
    pin_code = message.text.strip()

    token = await get_cashier_token(lic, pin_code)
    if not token:
        await message.answer("Не вдалося отримати токен касира. Перевірте введені дані.")
        await state.clear()
        return

    nm = await get_kasa_name(lic, token)
    user_kasas = kasas_data.get(user_id, [])
    idx = len(user_kasas) + 1
    if not nm or nm == 'Невідома каса':
        nm = f"Каса №{idx}"

    kasa_data = {
        'license_key': lic,
        'pin_code': pin_code,
        'cashier_token': token,
        'kasa_name': nm,
        'index': idx,
        'shift_id': None,
        'last_polled_shift_status': None,
        'last_receipt_datetime': None,
        'last_receipt_id': None,
        'shift_closed': True,
        'task_started': False,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'receipt_counter': 0
    }
    user_kasas.append(kasa_data)
    kasas_data[user_id] = user_kasas
    save_kasas_data(kasas_data)

    st_msg = await get_shift_status_msg(kasa_data, idx)
    await message.answer(f"Каса '{nm}' додана.\n{st_msg}")

    await state.clear()
    await start_background_polling(user_id)

def register_add_kasa_handlers(dp):
    dp.message.register(cmd_add_kasa, Command('add_kasa'))
    dp.message.register(process_license_key, StateFilter(AddKasaStates.waiting_for_license_key))
    dp.message.register(process_pin_code, StateFilter(AddKasaStates.waiting_for_pin_code))