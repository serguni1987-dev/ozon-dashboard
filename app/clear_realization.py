import sqlite3
import os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
n = con.execute("DELETE FROM monthly_realization_rows WHERE month = '2026-08'").rowcount
con.commit()
con.close()
print(f"[OK] Удалено: {n}")
