import os
from dateutil.parser import parser
import json
import re
from datetime import datetime
from config.settings import TOKEN_FILE, KASAS_FILE, TELEGRAM_TOKEN_REGEX

def check_or_create_token_file():
    if not os.path.exists(TOKEN_FILE):
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'w') as f:
            json.dump({"TELEGRAM_TOKEN": ""}, f)
        raise FileNotFoundError(f"Створено {TOKEN_FILE}. Заповніть токен!")
    
    with open(TOKEN_FILE) as f:
        data = json.load(f)
        if not re.match(TELEGRAM_TOKEN_REGEX, data.get("TELEGRAM_TOKEN", "")):
            raise ValueError("Невірний формат Telegram токена!")

def load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["TELEGRAM_TOKEN"]

def load_kasas_data():
    if not os.path.exists(KASAS_FILE):
        return {}

    with open(KASAS_FILE) as f:
        data = json.load(f)
        for user_id, kasas in data.items():
            for kasa in kasas:
                # Ініціалізація обов'язкових полів
                kasa.setdefault('shift_id', None)
                kasa.setdefault('last_polled_shift_status', None)
                kasa.setdefault('last_receipt_datetime', None)
                kasa.setdefault('shift_closed', True)
                kasa.setdefault('task_started', False)
                
                # Конвертація строкового часу в об'єкт datetime
                if isinstance(kasa.get('last_receipt_datetime'), str):
                    try:
                        kasa['last_receipt_datetime'] = parser.isoparse(kasa['last_receipt_datetime'])
                    except:
                        kasa['last_receipt_datetime'] = None
        return data

def save_kasas_data(data):
    sanitized = {}
    for user_id, kasas in data.items():
        sanitized[user_id] = [{
            'license_key': k['license_key'],
            'pin_code': k['pin_code'],
            'kasa_name': k['kasa_name'],
            'shift_id': k.get('shift_id'),
            'last_receipt_datetime': (
                k['last_receipt_datetime'].isoformat()
                if isinstance(k.get('last_receipt_datetime'), datetime)
                else None
            ),
            'last_receipt_id': k.get('last_receipt_id')
        } for k in kasas]
    
    os.makedirs(os.path.dirname(KASAS_FILE), exist_ok=True)
    with open(KASAS_FILE, 'w') as f:
        json.dump(sanitized, f, indent=2)