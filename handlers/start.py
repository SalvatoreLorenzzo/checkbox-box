import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime, timezone
from services.checkbox_api import (
    get_cashier_token,
    get_current_shift_id,
    get_shift_info,
    get_recent_receipts
)
from utils.storage import load_kasas_data, save_kasas_data
from utils.format_helpers import format_receipt_info, format_shift_statistics

logger = logging.getLogger(__name__)
kasas_data = load_kasas_data()
bot: Bot = None
dp: Dispatcher = None

async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    user_kasas = kasas_data.get(user_id, [])
    if not user_kasas:
        await message.answer("У вас немає доданих кас. Спочатку виконайте /add_kasa.")
        return
    await message.answer("Перевіряю стан кас...")
    for kasa_info in user_kasas:
        kasa_info['task_started'] = False
        kasa_info['last_polled_shift_status'] = None
        kasa_info['shift_id'] = None
        kasa_info['shift_closed'] = True
    save_kasas_data(kasas_data)
    await start_background_polling(user_id)

async def cmd_list_kasas(message: types.Message):
    user_id = str(message.from_user.id)
    user_kasas = kasas_data.get(user_id, [])
    if not user_kasas:
        await message.answer("У вас ще немає доданих кас.")
        return
    lines = ["Ваші каси:"]
    for idx, k in enumerate(user_kasas, start=1):
        nm = k.get('kasa_name', f"Каса №{idx}")
        lines.append(f"{idx}. {nm}")
    await message.answer("\n".join(lines))

async def get_shift_status_msg(kasa_info, idx=1):
    license_key = kasa_info['license_key']
    pin_code = kasa_info['pin_code']
    if not kasa_info.get('cashier_token'):
        kasa_info['cashier_token'] = await get_cashier_token(license_key, pin_code)
    kasa_name = kasa_info.get('kasa_name', f"Kаса №{idx}")
    shift_id = await get_current_shift_id(license_key, kasa_info['cashier_token'])
    if not shift_id:
        return f"На касі '{kasa_name}' зміна закрита."
    inf = await get_shift_info(license_key, kasa_info['cashier_token'], shift_id)
    if not inf:
        return f"Не вдалося отримати інформацію про зміну на касі '{kasa_name}'."
    st = inf.get('status','UNKNOWN')
    if st == 'OPENED':
        srl = inf.get('serial','N/A')
        return f"На касі '{kasa_name}' відкрита зміна №{srl}."
    return f"На касі '{kasa_name}' зміна має статус '{st}'."

async def start_background_polling(user_id):
    user_kasas = kasas_data.get(user_id, [])
    for kasa_info in user_kasas:
        if not kasa_info.get('task_started'):
            kasa_info['task_started'] = True
            asyncio.create_task(poll_kasa_loop(user_id, kasa_info))

async def poll_kasa_loop(user_id, kasa_info):
    while True:
        try:
            await handle_shift_and_receipts(user_id, kasa_info)
            await asyncio.sleep(30)
        except Exception as e:
            logger.exception(f"[poll_kasa_loop] {e}")
            await asyncio.sleep(30)

async def handle_shift_and_receipts(user_id, kasa):
    lic = kasa['license_key']
    pin = kasa['pin_code']
    if not kasa.get('cashier_token'):
        kasa['cashier_token'] = await get_cashier_token(lic, pin)
    sid = await get_current_shift_id(lic, kasa['cashier_token'])
    new_status = 'CLOSED'
    shift_data = None
    if sid:
        shift_data = await get_shift_info(lic, kasa['cashier_token'], sid)
        if shift_data and shift_data.get('status') == 'OPENED':
            new_status = 'OPENED'
    old_status = kasa.get('last_polled_shift_status')
    kasa['last_polled_shift_status'] = new_status
    k_name = kasa.get('kasa_name','N/A')
    if new_status == 'OPENED':
        if old_status != 'OPENED':
            kasa['shift_id'] = sid
            kasa['shift_closed'] = False
            if not kasa.get('last_receipt_datetime'):
                opened_at = shift_data.get('opened_at')
                if opened_at:
                    import dateutil.parser
                    kasa['last_receipt_datetime'] = dateutil.parser.isoparse(opened_at)
                else:
                    kasa['last_receipt_datetime'] = datetime.now(timezone.utc)
            kasa['last_receipt_id'] = None
            logger.info(f"SHIFT OPEN for '{k_name}', baseline = {kasa['last_receipt_datetime']}")
            await bot.send_message(user_id, f"Зміна відкрита на касі '{k_name}'.")
        await fetch_new_receipts(user_id, kasa)
    else:
        if old_status == 'OPENED':
            if kasa.get('shift_id'):
                recs_left = await get_recent_receipts(
                    lic,
                    kasa['cashier_token'],
                    kasa['shift_id'],
                    kasa.get('last_receipt_datetime') or datetime.now(timezone.utc),
                    datetime.now(timezone.utc)
                )
                await send_shift_summary(user_id, recs_left, kasa)
            kasa['shift_id'] = None
            kasa['shift_closed'] = True
            kasa['last_receipt_datetime'] = None
            kasa['last_receipt_id'] = None
            logger.info(f"SHIFT CLOSE for '{k_name}'")
            await bot.send_message(user_id, f"Зміна закрита на касі '{k_name}'.")
    save_kasas_data(kasas_data)

async def fetch_new_receipts(user_id, kasa):
    if not kasa.get('shift_id'):
        return
    lic = kasa['license_key']
    token = kasa['cashier_token']
    sid = kasa['shift_id']
    k_name = kasa.get('kasa_name','N/A')
    from_dt = kasa.get('last_receipt_datetime') or datetime.now(timezone.utc)
    import dateutil.parser
    if isinstance(from_dt, str):
        from_dt = dateutil.parser.isoparse(from_dt)
    to_dt = datetime.now(timezone.utc)
    receipts = await get_recent_receipts(lic, token, sid, from_dt, to_dt)
    def best_time(r):
        return r.get('modified_at') or r.get('created_at')
    receipts.sort(key=lambda x: (best_time(x), x.get('id')))
    last_dt = kasa.get('last_receipt_datetime')
    if isinstance(last_dt, str):
        last_dt = dateutil.parser.isoparse(last_dt)
    last_id = kasa.get('last_receipt_id')
    new_list = []
    for r in receipts:
        t_str = best_time(r)
        if not t_str or not r.get('id'):
            continue
        t_parsed = dateutil.parser.isoparse(t_str)
        if not last_dt or t_parsed > last_dt:
            new_list.append(r)
        elif t_parsed == last_dt and r['id'] != last_id:
            new_list.append(r)
    if new_list:
        for item in new_list:
            await send_one_receipt(user_id, item, kasa)
        last_obj = new_list[-1]
        last_t = best_time(last_obj)
        if last_t:
            kasa['last_receipt_datetime'] = dateutil.parser.isoparse(last_t)
        kasa['last_receipt_id'] = last_obj['id']
        logger.info(f"Fetched {len(new_list)} new receipts on '{k_name}'")
    else:
        logger.debug(f"No new receipts found on '{k_name}'")
    save_kasas_data(kasas_data)

async def send_one_receipt(user_id, rc, kasa):
    rid = rc.get('id','???')
    kasa['receipt_counter'] = kasa.get('receipt_counter',0) + 1
    txt = format_receipt_info(rc, kasa.get('kasa_name','N/A'), kasa['receipt_counter'])
    from services.checkbox_api import get_receipt_pdf
    pdf_bin = await get_receipt_pdf(kasa, rid)
    if pdf_bin:
        from aiogram.types import BufferedInputFile
        fobj = BufferedInputFile(pdf_bin, filename=f"receipt_{rid}.pdf")
        await bot.send_document(user_id, fobj, caption=txt)
    else:
        await bot.send_message(user_id, txt)

async def send_shift_summary(user_id, receipts, kasa):
    if not receipts:
        return
    txt = format_shift_statistics(receipts, kasa.get('kasa_name','N/A'))
    await bot.send_message(user_id, txt)

def register_start_handlers(dispatcher: Dispatcher, bot_instance: Bot):
    global bot, dp
    bot = bot_instance
    dp = dispatcher
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(cmd_list_kasas, Command('list_kasas'))