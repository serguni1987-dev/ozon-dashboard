import sqlite3
con = sqlite3.connect("ozon.db")
row = con.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM sales_daily").fetchone()
print(f"Первая дата:  {row[0]}")
print(f"Последняя:    {row[1]}")
print(f"Дней с данными: {row[2]}")

# Сколько всего SKU
row = con.execute("SELECT COUNT(DISTINCT sku) FROM sales_daily WHERE orders_units > 0").fetchone()
print(f"SKU с продажами: {row[0]}")

# По месяцам
print("\nПо месяцам:")
for r in con.execute("""
    SELECT substr(date, 1, 7) AS month,
           COUNT(DISTINCT date) AS days,
           SUM(revenue) AS rev,
           SUM(orders_units) AS orders
    FROM sales_daily
    GROUP BY month
    ORDER BY month
"""):
    print(f"  {r[0]}  дней: {r[1]:>3}, выручка: {r[2]:>10,.0f} ₽, заказов: {r[3]}")
con.close()
