import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
n1 = con.execute("""
    DELETE FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
""").rowcount
n2 = con.execute("""
    DELETE FROM accruals_services
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
""").rowcount
con.commit()
con.close()
print(f"[OK] Удалено accruals: {n1}, services: {n2}")
