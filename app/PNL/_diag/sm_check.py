import sqlite3

con = sqlite3.connect(r'C:\Users\sergu\Desktop\проект\app\ozon.db')

print('=== Все строки SM002180215 в monthly_realization_rows 2026-02 ===')
for r in con.execute("""
    SELECT id, sku, offer_id, quantity, is_return, seller_price, sale_price,
           item_name
    FROM monthly_realization_rows
    WHERE month='2026-02' AND sku = 1566289468
    ORDER BY id
"""):
    print(r)

print('\n=== Итого по этому SKU ===')
for r in con.execute("""
    SELECT is_return, COUNT(*) AS rows, SUM(quantity) AS qty
    FROM monthly_realization_rows
    WHERE month='2026-02' AND sku = 1566289468
    GROUP BY is_return
"""):
    print(r)

print('\n=== Все продажи SM002180215 за 2026 по месяцам ===')
for r in con.execute("""
    SELECT month, is_return, SUM(quantity) AS qty
    FROM monthly_realization_rows
    WHERE sku = 1566289468
    GROUP BY month, is_return
    ORDER BY month
"""):
    print(r)

con.close()