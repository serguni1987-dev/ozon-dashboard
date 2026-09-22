import sqlite3
c = sqlite3.connect("ozon.db")
rows = c.execute("""
    SELECT sku, offer_id, name FROM products WHERE sku = 1331070246
""").fetchall()
print("SKU 1331070246:", rows)

# Также все продажи этого SKU за 2026-09-01..05
rows2 = c.execute("""
    SELECT date, revenue, orders_units FROM sales_daily
    WHERE sku = 1331070246 AND date BETWEEN '2026-09-01' AND '2026-09-05'
    ORDER BY date
""").fetchall()
print("Продажи:", rows2)
