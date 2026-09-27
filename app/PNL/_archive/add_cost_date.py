import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(products)")]

if "cost_date" not in cols:
    con.execute("ALTER TABLE products ADD COLUMN cost_date TEXT")
    con.commit()
    print("[OK] Колонка cost_date добавлена в products")
else:
    print("[i] cost_date уже есть")

# Проставим сегодняшнюю дату для тех, где уже есть себестоимость
n = con.execute("""
    UPDATE products SET cost_date = '2026-09-24'
    WHERE is_own = 1 AND cost_price > 0 AND cost_date IS NULL
""").rowcount
con.commit()
print(f"[OK] Проставлено cost_date = 2026-09-24 у {n} SKU")

con.close()
