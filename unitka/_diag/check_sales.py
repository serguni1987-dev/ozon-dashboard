import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== СХЕМА sales_daily ===")
for row in cur.execute("PRAGMA table_info(sales_daily)"):
    print(f"  {row[1]:25} {row[2]}")

print("\n=== ПЕРВЫЕ 3 СТРОКИ sales_daily ===")
cur.execute("SELECT * FROM sales_daily LIMIT 3")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for row in cur.fetchall():
    print(" | ".join(str(x)[:15] for x in row))

print("\n=== ИТОГИ по sales_daily (за весь период) ===")
cur.execute("SELECT COUNT(*) as rows, COUNT(DISTINCT date) as days, COUNT(DISTINCT sku) as skus FROM sales_daily")
r = cur.fetchone()
print(f"Строк: {r[0]} | Уникальных дат: {r[1]} | Уникальных SKU: {r[2]}")

# Проверяем ключевые суммы (если колонки есть)
try:
    cur.execute("SELECT SUM(revenue), SUM(ordered_units), SUM(ordered_amount) FROM sales_daily")
    r = cur.fetchone()
    print(f"\nSUM(revenue): {r[0]}")
    print(f"SUM(ordered_units): {r[1]}")
    print(f"SUM(ordered_amount): {r[2]}")
except Exception as e:
    print(f"\nОшибка суммы: {e}")
con.close()