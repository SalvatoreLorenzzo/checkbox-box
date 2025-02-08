# utils/storage.py
import os
import sys
import json
import re
from datetime import datetime
from config.settings import TOKEN_FILE, KASAS_FILE, TELEGRAM_TOKEN_REGEX

def check_or_create_token_file():
    if not os.path.exists(TOKEN_FILE):
        print(f"[INFO] '{TOKEN_FILE}' not found. Creating an empty file.")
        data = {"TELEGRAM_TOKEN": ""}
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("Please open token.json, insert your TELEGRAM_TOKEN, and restart.")
        sys.exit(1)
    else:
        if os.path.getsize(TOKEN_FILE) == 0:
            print("[INFO] token.json is empty. Fill TELEGRAM_TOKEN.")
            sys.exit(1)
        else:
            try:
                with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                print("[ERROR] token.json is invalid JSON.")
                sys.exit(1)

            tg = data.get("TELEGRAM_TOKEN", "")
            if not tg:
                print("[ERROR] TELEGRAM_TOKEN is empty.")
                sys.exit(1)
            if not re.match(TELEGRAM_TOKEN_REGEX, tg):
                print("[ERROR] TELEGRAM_TOKEN not valid.")
                sys.exit(1)

def load_token():
    with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("TELEGRAM_TOKEN", "")

def load_kasas_data():
    if os.path.exists(KASAS_FILE):
        try:
            with open(KASAS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    else:
        return {}

def save_kasas_data(kasas_data):
    pkg = {}
    for user_id, kasas_list in kasas_data.items():
        new_list = []
        for k in kasas_list:
            kc = k.copy()
            kc.pop('task_started', None)
            kc.pop('cashier_token', None)
            kc.pop('last_shift_status', None)
            kc.pop('started_with_open_shift', None)
            kc.pop('started_at', None)
            kc.pop('receipt_counter', None)

            if isinstance(kc.get('last_receipt_datetime'), datetime):
                kc['last_receipt_datetime'] = kc['last_receipt_datetime'].isoformat()
            new_list.append(kc)
        pkg[user_id] = new_list

    os.makedirs(os.path.dirname(KASAS_FILE), exist_ok=True)
    with open(KASAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(pkg, f, ensure_ascii=False, indent=4)