import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== Чистка дублей в sales_daily ===")
before = cur.execute("SELECT COUNT(*) FROM sales_daily").fetchone()[0]
print(f"Было строк: {before}")

cur.execute("""
    DELETE FROM sales_daily
    WHERE rowid NOT IN (
        SELECT MIN(rowid)
        FROM sales_daily
        GROUP BY date, sku
    )
""")
con.commit()

after = cur.execute("SELECT COUNT(*) FROM sales_daily").fetchone()[0]
print(f"Стало строк: {after}")
print(f"Удалено дублей: {before - after}")

cur.execute("SELECT COUNT(*) FROM (SELECT date, sku, COUNT(*) as c FROM sales_daily GROUP BY date, sku HAVING c > 1)")
print(f"Осталось дублей: {cur.fetchone()[0]} (должно быть 0)")
con.close()