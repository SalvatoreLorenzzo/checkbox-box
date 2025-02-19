# -*- coding: utf-8 -*-
"""
handlers/start.py
"""

import asyncio
import logging
from datetime import datetime, timezone
import dateutil.parser
from config.settings import POLL_INTERVAL_OPEN, POLL_INTERVAL_CLOSED, DEBUG_SHIFT_LOG
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from services.checkbox_api import (
    get_cashier_token,
    get_current_shift_id,
    get_shift_info,
    get_recent_receipts
)
from utils.storage import load_kasas_data, save_kasas_data
from utils.format_helpers import format_receipt_info, format_shift_statistics

# Додамо параметри опитування та налаштування налагодження з налаштувань
from config.settings import POLL_INTERVAL_OPEN, POLL_INTERVAL_CLOSED, DEBUG_SHIFT_LOG, DEBUG_WITHDRAWAL_LOG

logger = logging.getLogger(__name__)
kasas_data = load_kasas_data()
bot: Bot = None
dp: Dispatcher = None

async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    user_kasas = kasas_data.get(user_id, [])
    if not user_kasas:
        await message.answer("❌ У вас немає доданих кас. Спочатку виконайте /add_kasa.")
        return

    # Перевіримо, чи вже запущено цикл опитування
    is_polling = any(kasa.get('task_started') for kasa in user_kasas)
    if is_polling:
        await message.answer("Бот вже працює. Перевіряю стан кас...")
    else:
        await message.answer("Перевіряю стан кас...")

    # Скидаємо лише необхідні поля, НЕ змінюючи last_receipt_datetime
    for kasa_info in user_kasas:
        kasa_info['task_started'] = False
        kasa_info['last_polled_shift_status'] = None
        kasa_info['shift_id'] = None
        kasa_info['shift_closed'] = True
    save_kasas_data(kasas_data)
    await start_background_polling(user_id)
    await message.answer("✅ Моніторинг запущено. Очікуйте сповіщення про зміни.")

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
    kasa_name = kasa_info.get('kasa_name', f"Каса №{idx}")
    shift_id = await get_current_shift_id(license_key, kasa_info['cashier_token'])
    if not shift_id:
        return f"На касі '{kasa_name}' зміна закрита."
    inf = await get_shift_info(license_key, kasa_info['cashier_token'], shift_id)
    if not inf:
        return f"Не вдалося отримати інформацію про зміну на касі '{kasa_name}'."
    st = inf.get('status', 'UNKNOWN')
    if st == 'OPENED':
        srl = inf.get('serial', 'N/A')
        return f"На касі '{kasa_name}' відкрита зміна №{srl}."
    return f"На касі '{kasa_name}' зміна має статус '{st}'."

async def start_background_polling(user_id):
    user_kasas = kasas_data.get(user_id, [])
    for kasa_info in user_kasas:
        if not kasa_info.get('task_started'):
            kasa_info['task_started'] = True
            asyncio.create_task(poll_kasa_loop(user_id, kasa_info))
    save_kasas_data(kasas_data)

async def poll_kasa_loop(user_id, kasa_info):
    kasa_name = kasa_info.get('kasa_name', 'N/A')
    while True:
        try:
            logger.info(f"[poll_kasa_loop] Polling kasa: {kasa_name} for user: {user_id}")
            await handle_shift_and_receipts(user_id, kasa_info)
            # Використовуємо різний інтервал в залежності від стану зміни
            if kasa_info.get('last_polled_shift_status') == 'OPENED':
                sleep_seconds = POLL_INTERVAL_OPEN
            else:
                sleep_seconds = POLL_INTERVAL_CLOSED
            await asyncio.sleep(sleep_seconds)
        except Exception as e:
            logger.exception(f"[poll_kasa_loop] Error polling kasa '{kasa_name}': {e}")
            await asyncio.sleep(10)

async def handle_shift_and_receipts(user_id, kasa):
    from datetime import datetime, timezone
    import dateutil.parser
    # (інші імпорти та початкова логіка залишаються без змін)
    lic = kasa['license_key']
    pin = kasa['pin_code']
    kasa_name = kasa.get('kasa_name', 'N/A')

    logger.info(f"[handle_shift_and_receipts] Handling kasa '{kasa_name}' for user: {user_id}")

    if not kasa.get('cashier_token'):
        logger.info(f"[handle_shift_and_receipts] Fetching cashier token for kasa '{kasa_name}'")
        kasa['cashier_token'] = await get_cashier_token(lic, pin)

    sid = None
    try:
        sid = await get_current_shift_id(lic, kasa['cashier_token'])
        logger.info(f"[handle_shift_and_receipts] Current shift ID for kasa '{kasa_name}': {sid}")
    except Exception as e:
        logger.error(f"[handle_shift_and_receipts] Failed to fetch shift ID for kasa '{kasa_name}': {e}")
        sid = None

    new_status = 'CLOSED'
    shift_data = None

    if sid:
        try:
            shift_data = await get_shift_info(lic, kasa['cashier_token'], sid)
            if DEBUG_SHIFT_LOG:
                logger.info(f"[handle_shift_and_receipts] Shift data for kasa '{kasa_name}': {shift_data}")
            else:
                logger.info(f"[handle_shift_and_receipts] Shift info fetched for kasa '{kasa_name}'")
        except Exception as e:
            logger.error(f"[handle_shift_and_receipts] Failed to fetch shift info for kasa '{kasa_name}': {e}")

    if shift_data:
        shift_status = shift_data.get('status', 'UNKNOWN')
        if shift_status == 'OPENED':
            new_status = 'OPENED'

    old_status = kasa.get('last_polled_shift_status')
    kasa['last_polled_shift_status'] = new_status

    # Формування часових діапазонів для запиту звітів
    if 'shift_start_datetime' in kasa and kasa['shift_start_datetime']:
        if isinstance(kasa['shift_start_datetime'], str):
            from_date_str = kasa['shift_start_datetime']
        else:
            from_date_str = kasa['shift_start_datetime'].isoformat()
    else:
        from_date_str = datetime.now(timezone.utc).isoformat()
    to_date_str = datetime.now(timezone.utc).isoformat()

# У відповідному блоці для OPENED
    if new_status == 'OPENED' and old_status != 'OPENED':
        kasa['shift_id'] = sid
        kasa['shift_closed'] = False
        if not kasa.get('shift_start_datetime'):
            opened_at = shift_data.get('opened_at') if shift_data else None
            if opened_at:
                kasa['shift_start_datetime'] = dateutil.parser.isoparse(opened_at)
            else:
                kasa['shift_start_datetime'] = datetime.now(timezone.utc)
        if not kasa.get('last_receipt_datetime'):
            kasa['last_receipt_datetime'] = kasa['shift_start_datetime']

        logger.info(f"[handle_shift_and_receipts] Shift opened for kasa '{kasa_name}' (ID: {sid})")
        await bot.send_message(user_id, f"Зміна відкрита на касі '{kasa_name}'.")
        
        # --- Отримання X звіту ---
        from_date_str = kasa['shift_start_datetime'].isoformat()
        to_date_str = datetime.now(timezone.utc).isoformat()
        from services.checkbox_api import get_report_receipt_info, get_receipt_pdf
        reports = await get_report_receipt_info(lic, kasa['cashier_token'], is_z_report=False, shift_id=sid,
                                               from_date=from_date_str, to_date=to_date_str)
        pdf_x = None
        if reports:
            for rep in reports:
                receipt_id = rep.get('last_receipt_id') or rep.get('id')
                logger.info(f"[handle_shift_and_receipts] Trying X report with receipt_id: {receipt_id}")
                pdf_x = await get_receipt_pdf(kasa, receipt_id)
                if pdf_x:
                    logger.info(f"[handle_shift_and_receipts] Successfully retrieved X report PDF for receipt_id: {receipt_id}")
                    break
            if pdf_x:
                from aiogram.types import BufferedInputFile
                x_file = BufferedInputFile(pdf_x, filename=f"x_report_{sid}.pdf")
                await bot.send_document(user_id, x_file, caption=f"X звіт для зміни ({sid})")
            else:
                logger.error(f"[handle_shift_and_receipts] Не вдалося отримати PDF для X звіту (перевірте звіти для shift {sid}).")
        else:
            logger.error(f"[handle_shift_and_receipts] Звіт X не знайдено для зміни ({sid}).")
            
    # --- Блок для CLOSED (аналогічно, для Z звіту) ---
    elif new_status == 'CLOSED' and old_status != 'CLOSED':
        await send_shift_summary(user_id, kasa)
        kasa['shift_id'] = None
        kasa['shift_closed'] = True
        kasa['last_receipt_datetime'] = None
        kasa.pop('shift_start_datetime', None)
        kasa['last_receipt_id'] = None
        kasa['receipt_counter'] = 0  # скидання лічильника чеків
        logger.info(f"[handle_shift_and_receipts] Shift closed for kasa '{kasa_name}'")
        await bot.send_message(user_id, f"На касі '{kasa_name}' зміна закрита.")
        
        from_date_str = kasa.get('shift_start_datetime').isoformat() if kasa.get('shift_start_datetime') else datetime.now(timezone.utc).isoformat()
        to_date_str = datetime.now(timezone.utc).isoformat()
        from services.checkbox_api import get_report_receipt_info, get_receipt_pdf
        reports = await get_report_receipt_info(lic, kasa['cashier_token'], is_z_report=True, shift_id=sid,
                                               from_date=from_date_str, to_date=to_date_str)
        pdf_z = None
        if reports:
            for rep in reports:
                receipt_id = rep.get('last_receipt_id') or rep.get('id')
                logger.info(f"[handle_shift_and_receipts] Trying Z report with receipt_id: {receipt_id}")
                pdf_z = await get_receipt_pdf(kasa, receipt_id)
                if pdf_z:
                    logger.info(f"[handle_shift_and_receipts] Successfully retrieved Z report PDF for receipt_id: {receipt_id}")
                    break
            if pdf_z:
                from aiogram.types import BufferedInputFile
                z_file = BufferedInputFile(pdf_z, filename=f"z_report_{sid}.pdf")
                await bot.send_document(user_id, z_file, caption=f"Z звіт для зміни ({sid})")
            else:
                logger.error(f"[handle_shift_and_receipts] Не вдалося отримати PDF для Z звіту (перевірте звіти для shift {sid}).")
        else:
            logger.error(f"[handle_shift_and_receipts] Звіт Z не знайдено для зміни ({sid}).")
    else:
        logger.info(f"[handle_shift_and_receipts] No change in shift status for kasa '{kasa_name}'")

    if new_status == 'OPENED':
        await fetch_new_receipts(user_id, kasa)

    save_kasas_data(kasas_data)

async def fetch_new_receipts(user_id, kasa):
    from config.settings import DEBUG_RECEIPT_INFO
    if not kasa.get('shift_id'):
        return

    lic = kasa['license_key']
    token = kasa['cashier_token']
    sid = kasa['shift_id']
    k_name = kasa.get('kasa_name', 'N/A')

    # При першому запуску встановлюємо стартову дату, відфільтровуючи чеки виводу (service_out != "0")
    if kasa.get('last_receipt_datetime') is None:
        far_past = datetime(2023, 1, 1, tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        all_receipts = await get_recent_receipts(lic, token, sid, far_past, now_utc)
        valid_receipts = []
        for r in all_receipts:
            service_out = str(r.get('service_out', '0')).strip()
            if DEBUG_RECEIPT_INFO:
                logger.info(f"[Init] Receipt {r.get('id')} info: service_out={service_out}, total_sum={r.get('total_sum')}, payments={r.get('payments')}")
            # Ігноруємо чеки виводу (service_out відмінне від "0")
            if service_out == "0":
                valid_receipts.append(r)
            else:
                logger.info(f"[Init] Ignoring receipt {r.get('id')} because service_out={service_out}")
        if valid_receipts:
            def best_time(r):
                return r.get('modified_at') or r.get('created_at')
            valid_receipts.sort(key=lambda x: (best_time(x), x.get('id')))
            last_rc = valid_receipts[-1]
            best_ts = best_time(last_rc)
            if best_ts:
                kasa['last_receipt_datetime'] = dateutil.parser.isoparse(best_ts)
                kasa['last_receipt_id'] = last_rc.get('id')
        save_kasas_data(kasas_data)
        return

    # Обробка нових чеків (якщо вже був встановлений last_receipt_datetime)
    from_dt = kasa['last_receipt_datetime']
    if isinstance(from_dt, str):
        from_dt = dateutil.parser.isoparse(from_dt)
    to_dt = datetime.now(timezone.utc)
    receipts = await get_recent_receipts(lic, token, sid, from_dt, to_dt)

    def best_time(r):
        return r.get('modified_at') or r.get('created_at')
    receipts.sort(key=lambda x: (best_time(x), x.get('id')))
    last_dt = from_dt
    last_id = kasa.get('last_receipt_id')
    new_list = []
    for r in receipts:
        rid = r.get('id')
        t_str = best_time(r)
        if not t_str or not rid:
            continue
        t_parsed = dateutil.parser.isoparse(t_str)
        service_out = str(r.get('service_out', '0')).strip()
        if DEBUG_RECEIPT_INFO:
            logger.info(f"[Fetch] Processing receipt {rid}: service_out={service_out}, total_sum={r.get('total_sum')}, payments={r.get('payments')}")
        # Якщо значення не рівне "0" – це чек виводу, ігноруємо його
        if service_out != "0":
            logger.info(f"[Fetch] Ignoring receipt {rid} because service_out={service_out}")
            continue
        if t_parsed > last_dt or (t_parsed == last_dt and rid != last_id):
            new_list.append(r)

    if new_list:
        for item in new_list:
            await send_one_receipt(user_id, item, kasa)  # Виклик передаємо як позиційний аргумент
        last_obj = new_list[-1]
        last_t = best_time(last_obj)
        if last_t:
            kasa['last_receipt_datetime'] = dateutil.parser.isoparse(last_t)
        kasa['last_receipt_id'] = last_obj['id']
        logger.info(f"[Fetch] Fetched {len(new_list)} new receipts on '{k_name}'")
    else:
        logger.info(f"[Fetch] No new receipts found on '{k_name}'")

    save_kasas_data(kasas_data)

async def send_one_receipt(user_id, rc, kasa):
    from config.settings import DEBUG_RECEIPT_INFO, DEBUG_RECEIPT_DETAILS
    receipt_id = rc.get('id', '???')
    
    # Отримання повної інформації про чек через API
    from services.checkbox_api import get_receipt_info, get_receipt_pdf
    full_receipt_info = await get_receipt_info(receipt_id, kasa['license_key'], kasa['cashier_token'])
    if full_receipt_info is None:
        logger.error(f"[SendOne] Failed to retrieve full info for receipt {receipt_id}, skipping.")
        return

    # Перевірка типу чека: ігноруємо, якщо тип SERVICE_OUT або SERVICE_IN
    receipt_type = full_receipt_info.get('type', '').upper()
    if receipt_type in ["SERVICE_OUT", "SERVICE_IN"]:
        logger.info(f"[SendOne] Ignoring receipt {receipt_id} due to type {receipt_type}.")
        return

    if DEBUG_RECEIPT_DETAILS:
        logger.info(f"[SendOne] Full receipt info for {receipt_id}: {full_receipt_info}")

    # Додатковий вивід базових деталей, якщо увімкнено DEBUG_RECEIPT_INFO
    receipt_details_partial = (
        f"ID: {rc.get('id')}, "
        f"service_out: {rc.get('service_out')}, "
        f"total_sum: {rc.get('total_sum')}, "
        f"payments: {rc.get('payments')}"
    )
    if DEBUG_RECEIPT_INFO:
        logger.info(f"[SendOne] Processing receipt: {receipt_details_partial}")

    # Стандартна обробка чека
    kasa['receipt_counter'] = kasa.get('receipt_counter', 0) + 1
    txt = format_receipt_info(rc, kasa.get('kasa_name', 'N/A'), kasa['receipt_counter'])
    pdf_bin = await get_receipt_pdf(kasa, receipt_id)
    if pdf_bin:
        from aiogram.types import BufferedInputFile
        fobj = BufferedInputFile(pdf_bin, filename=f"receipt_{receipt_id}.pdf")
        await bot.send_document(user_id, fobj, caption=txt)
    else:
        await bot.send_message(user_id, txt)

async def send_withdrawal_receipt(user_id, receipt, kasa):
    # Функція залишається, але її виклик більше не відбувається
    kasa_name = kasa.get('kasa_name', 'N/A')
    service_out_amount = receipt.get('service_out', 0) / 100
    msg = (
        f"💵 <b>Виведення грошей</b>\n"
        f"Каса: {kasa_name}\n"
        f"Сума: {service_out_amount:.2f} грн\n"
        f"Час: {receipt.get('created_at', 'N/A')}"
    )
    await bot.send_message(user_id, msg)
    logger.info(f"Sent withdrawal receipt for kasa '{kasa_name}' (amount={service_out_amount:.2f} грн)")

async def send_shift_summary(user_id, kasa):
    """
    Формуємо звіт за зміною, обчислюючи суму продажів і кількість чеків,
    ігноруючи чеки з типом SERVICE_OUT та SERVICE_IN.
    """
    lic = kasa['license_key']
    token = kasa['cashier_token']
    sid = kasa.get('shift_id')
    if not sid:
        await bot.send_message(user_id, "Немає активної зміни для формування звіту.")
        return

    # Визначаємо початковий час зміни (якщо встановлено, інакше використовується last_receipt_datetime)
    if 'shift_start_datetime' in kasa and kasa['shift_start_datetime']:
        start_time = kasa['shift_start_datetime']
    else:
        start_time = kasa.get('last_receipt_datetime')
    if isinstance(start_time, str):
        start_time = dateutil.parser.isoparse(start_time)
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)

    receipts = await get_recent_receipts(lic, token, sid, start_time, end_time)
    filtered_receipts = []
    for r in receipts:
        r_type = str(r.get('type', '')).upper()
        if r_type in ("SERVICE_OUT", "SERVICE_IN"):
            logger.info(f"[Report] Ignoring receipt {r.get('id')} with type {r_type}")
            continue
        filtered_receipts.append(r)

    if filtered_receipts:
        cash_total = 0
        card_total = 0
        overall_total = 0
        for r in filtered_receipts:
            receipt_total = r.get('total_sum', 0)
            overall_total += receipt_total
            payments = r.get('payments', [])
            sum_payments = sum(p.get('value', 0) for p in payments)
            if sum_payments == 0:
                if payments:
                    pay_type = payments[0].get('type', '').upper()
                    if pay_type == 'CASH':
                        cash_total += receipt_total
                    elif pay_type in ('CARD', 'CASHLESS'):
                        card_total += receipt_total
                continue
            for p in payments:
                pay_type = p.get('type', '').upper()
                allocated = (p.get('value', 0) / sum_payments) * receipt_total
                if pay_type == 'CASH':
                    cash_total += allocated
                elif pay_type in ('CARD', 'CASHLESS'):
                    card_total += allocated

        overall_total /= 100.0
        cash_total /= 100.0
        card_total /= 100.0

        report_text = (f"Звіт за зміною на касі '{kasa.get('kasa_name', 'N/A')}':\n"
                       f"Кількість чеків: {len(filtered_receipts)}\n"
                       f"Сума продаж (готівка): {cash_total:.2f} грн\n"
                       f"Сума продаж (картки): {card_total:.2f} грн\n"
                       f"Загальна сума продаж: {overall_total:.2f} грн")
        await bot.send_message(user_id, report_text)
    else:
        await bot.send_message(user_id, f"На касі '{kasa.get('kasa_name', 'N/A')}' немає чеків для звіту.")

def register_start_handlers(dispatcher: Dispatcher, bot_instance: Bot):
    global bot, dp
    bot = bot_instance
    dp = dispatcher
    dp.message.register(cmd_start, Command('start'))
    dp.message.register(cmd_list_kasas, Command('list_kasas'))