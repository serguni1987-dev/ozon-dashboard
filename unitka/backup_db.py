"""unitka/backup_db.py — резервное копирование ozon.db."""
import os
import shutil
import logging
from datetime import datetime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(APP_DIR, "app", "ozon.db")
BACKUP_DIR = os.path.join(APP_DIR, "_backups")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"ozon_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    size_mb = os.path.getsize(backup_path) / (1024 * 1024)
    logger.info("Бэкап создан: %s (%.1f МБ)", backup_path, size_mb)

    # Оставляем только 7 последних бэкапов
    backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("ozon_")],
        key=lambda x: os.path.getmtime(x),
        reverse=True,
    )
    for old in backups[7:]:
        os.remove(old)
        logger.info("Удалён старый бэкап: %s", os.path.basename(old))


if __name__ == "__main__":
    backup()
