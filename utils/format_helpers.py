# utils/format_helpers.py
from dateutil import parser
from datetime import datetime
import pytz

def format_receipt_info(receipt, kasa_name, custom_number=None):
    s = receipt.get('serial', 'N/A')
    ts_str = receipt.get('created_at', 'N/A')
    total_sum = receipt.get('total_sum', 0) / 100
    pm = []
    for p in receipt.get('payments', []):
        t = p.get('type', '').upper()
        if t in ('CASH', 'CARD', 'CASHLESS'):
            pm.append(p.get('type_label', t))

    pay_methods = ', '.join(pm) if pm else 'N/A'
    local_ts = ts_str
    if ts_str != 'N/A':
        try:
            d_utc = parser.isoparse(ts_str)
            kyiv_tz = pytz.timezone("Europe/Kiev")
            d_local = d_utc.astimezone(kyiv_tz)
            local_ts = d_local.strftime('%d.%m.%Y %H:%M:%S')
        except:
            pass

    lines = []
    lines.append(f"Каса: {kasa_name}")
    if custom_number:
        lines.append(f"Чек #{custom_number}")
    lines.append(f"Serial: {s}")
    lines.append(f"Сума: {total_sum:.2f} грн")
    lines.append(f"Оплата: {pay_methods}")
    lines.append(f"Час: {local_ts}")
    return "\n".join(lines)

def format_shift_statistics(receipts, kasa_name):
    total_cash = 0.0
    total_card = 0.0
    count = 0
    for r in receipts:
        for p in r.get('payments', []):
            t = p.get('type', '').upper()
            val = p.get('value', 0) / 100
            if t == 'CASH':
                total_cash += val
            elif t in ('CARD', 'CASHLESS'):
                total_card += val
        count += 1
    total_all = total_cash + total_card
    msg = (
        f"Статистика на касі '{kasa_name}':\n"
        f"Чеків: {count}\n"
        f"— Готівкою: {total_cash:.2f} грн\n"
        f"— Карткою/Безготівково: {total_card:.2f} грн\n"
        f"Всього: {total_all:.2f} грн"
    )
    return msg