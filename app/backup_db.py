"""
backup_db.py — резервная копия ozon.db в backups/.
Запускается из run.py автоматически. Хранит 30 последних копий.
"""
import os
import shutil
from datetime import datetime

DB = "ozon.db"
BACKUP_DIR = "backups"
MAX_KEEP = 30


def main():
    if not os.path.exists(DB):
        print(f"[WARN] {DB} не найден, backup пропущен")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    target = os.path.join(BACKUP_DIR, f"ozon_{stamp}.db")

    shutil.copy2(DB, target)
    size_kb = os.path.getsize(target) / 1024
    print(f"[OK] Backup: {target} ({size_kb:.0f} KB)")

    files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("ozon_") and f.endswith(".db")],
        reverse=True,
    )
    for old in files[MAX_KEEP:]:
        os.remove(os.path.join(BACKUP_DIR, old))
        print(f"     Удалён старый: {old}")

    print(f"     Всего копий: {min(len(files), MAX_KEEP)}")


if __name__ == "__main__":
    main()
