# config/settings.py
import re

BASE_URL = 'https://api.checkbox.in.ua/api/v1'
CLIENT_NAME = 'YourIntegrationName'
CLIENT_VERSION = '1.0'

TOKEN_FILE = 'data/token.json'
KASAS_FILE = 'data/kasas.json'

TELEGRAM_TOKEN_REGEX = r'^\d+:.+'