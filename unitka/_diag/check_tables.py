import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== СРАВНЕНИЕ ТАБЛИЦ ===")
for table in ("sales_daily", "analytics_manual"):
    try:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        max_d = cur.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
        skus = cur.execute(f"SELECT COUNT(DISTINCT sku) FROM {table}").fetchone()[0]
        print(f"{table:20} | строк: {cnt:>7} | SKU: {skus:>5} | макс. дата: {max_d}")
    except Exception as e:
        print(f"{table:20} | ОШИБКА: {e}")

print("\n=== КТО ЧИТАЕТ ИЗ КАКОЙ ТАБЛИЦЫ? ===")
import subprocess
files = ["calc_funnel.py", "calc_abc_xyz.py", "calc_unit_summary.py", "calc_pulse.py"]
for f in files:
    path = config.APP_DIR.parent / "unitka" / f
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    if "analytics_manual" in text:
        print(f"  {f:25} → читает analytics_manual")
    elif "sales_daily" in text:
        print(f"  {f:25} → читает sales_daily")
    else:
        print(f"  {f:25} → не использует ни то, ни другое")
con.close()