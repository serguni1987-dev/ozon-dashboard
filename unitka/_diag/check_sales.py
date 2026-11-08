import sqlite3
c = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
r = c.execute("""
    SELECT MIN(date) AS mn, MAX(date) AS mx,
           COUNT(DISTINCT date) AS d,
           SUM(orders_units) AS o, SUM(cancelled) AS cc,
           SUM(returned_by_order_date) AS rt
    FROM sales_daily WHERE date BETWEEN '2026-09-01' AND '2026-10-03'
""").fetchone()
print("min:", r[0], "max:", r[1], "дней:", r[2], "заказов:", r[3], "отмен:", r[4], "возвратов:", r[5])
