import os
from pathlib import Path

BOT_TOKEN = "8247381561:AAGvwwAIEsX0zfqzPUdZ0QlWH2kUlbrJAYI"

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

SIZE_ORDER = [42, 44, 46, 48, 50, 52, 54, 56]

MAX_FILE_SIZE = 50 * 1024 * 1024 * 1024 * 1024  # 50 GB

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"