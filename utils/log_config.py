import os
import glob
import logging
import logging.handlers
from datetime import datetime
from config.settings import LOG_DIR, MAX_LOG_FILES, LOG_FORMAT, LOG_LEVEL

def setup_logging():
    # Переконаємось, що каталог для логів існує
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # Формуємо назву нового лог-файлу із відміткою часу
    log_filename = os.path.join(LOG_DIR, datetime.now().strftime("bot_%Y%m%d_%H%M%S.log"))

    # Налаштовуємо кореневий логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Форматувальник для логів
    formatter = logging.Formatter(LOG_FORMAT)

    # Створюємо FileHandler із новою назвою файлу
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Додаємо StreamHandler для виводу в консоль (опціонально)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Очистка старих лог-файлів (якщо їх більше MAX_LOG_FILES)
    log_files = sorted(glob.glob(os.path.join(LOG_DIR, "bot_*.log")))
    if len(log_files) > MAX_LOG_FILES:
        files_to_remove = log_files[: len(log_files) - MAX_LOG_FILES]
        for f in files_to_remove:
            try:
                os.remove(f)
            except Exception as e:
                logger.error(f"Error removing old log file {f}: {e}")

if __name__ == '__main__':
    # Для тестування модуля виклик setup_logging
    setup_logging()
    logging.info("Logging setup is complete.")