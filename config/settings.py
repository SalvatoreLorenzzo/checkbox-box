# config/settings.py
BASE_URL = 'https://api.checkbox.in.ua/api/v1'
CLIENT_NAME = 'YourIntegrationName'
CLIENT_VERSION = '1.0'

TOKEN_FILE = 'data/token.json'
KASAS_FILE = 'data/kasas.json'

TELEGRAM_TOKEN_REGEX = r'^\d+:.+'

# Нові налаштування для опитування
POLL_INTERVAL_OPEN = 10      # опитування для відкритої зміни – 10 секунд
POLL_INTERVAL_CLOSED = 30    # опитування для закритої зміни – 30 секунд

# Налаштування для детального виводу інформації про зміну в консоль
DEBUG_SHIFT_LOG = False
# Налаштування для детального виводу інформації про чек в консоль
DEBUG_RECEIPT_INFO = True

DEBUG_WITHDRAWAL_LOG = False

# config/settings.py
DEBUG_RECEIPT_DETAILS = True