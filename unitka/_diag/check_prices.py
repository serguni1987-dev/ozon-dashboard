import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== current_prices ===")
try:
    cnt = cur.execute("SELECT COUNT(*) FROM current_prices").fetchone()[0]
    print(f"Строк: {cnt}")
    if cnt > 0:
        print("Пример:", cur.execute("SELECT sku, price FROM current_prices LIMIT 3").fetchall())
except Exception as e:
    print(f"Ошибка: {e}")

print("\n=== Проверка OCP013E4 в realization_daily ===")
r = cur.execute("SELECT sku, date, sale_price, quantity FROM realization_daily WHERE sku = 1288893361 LIMIT 3").fetchall()
for row in r:
    print(row)
con.close()