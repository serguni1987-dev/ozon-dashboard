import sqlite3
c = sqlite3.connect("ozon.db")
rows = c.execute("""
    SELECT sd.sku, sd.date, sd.revenue, sd.orders_units, p.offer_id
    FROM sales_daily sd
    JOIN products p ON p.sku = sd.sku
    WHERE p.offer_id = 'OCE013E4'
    ORDER BY sd.date
    LIMIT 10
""").fetchall()
for r in rows:
    print(r)
