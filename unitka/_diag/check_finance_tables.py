import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== Таблицы в базе, связанные с деньгами ===")
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    if any(x in t.lower() for x in ['trans', 'payout', 'finance', 'cash', 'money', 'debit']):
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            max_d = cur.execute(f"SELECT MAX(date) FROM {t}").fetchone()[0] if cnt > 0 else "—"
            print(f"{t:30} | строк: {cnt:>6} | последняя дата: {max_d}")
        except Exception as e:
            print(f"{t:30} | ошибка: {str(e)[:50]}")

print("\n=== ВСЕ таблицы в базе (для полноты) ===")
for t in sorted(tables):
    print(f"  {t}")
con.close()