import sqlite3

con = sqlite3.connect(r'C:\Users\sergu\Desktop\проект\app\ozon.db')

print('=== Все возвраты января (сырые строки) ===')
for r in con.execute("""
    SELECT id, sku, offer_id, quantity, item_name
    FROM monthly_realization_rows
    WHERE month='2026-01' AND is_return=1
    ORDER BY id
"""):
    print(r)

print('\n=== Есть ли Mood of Paris в продажах января? ===')
for r in con.execute("""
    SELECT sku, offer_id, quantity, is_return
    FROM monthly_realization_rows
    WHERE month='2026-01'
      AND (offer_id LIKE 'MP%' OR item_name LIKE '%Mood of Paris%')
"""):
    print(r)

print('\n=== Все SKU Mood of Paris из product_cost_history ===')
for r in con.execute("""
    SELECT sku, cost_price, date_from
    FROM product_cost_history
    WHERE cost_price = 3271
    ORDER BY sku
"""):
    print(r)

print('\n=== Возвраты в raw_json (если сохранён) ===')
r = con.execute("""
    SELECT raw_json FROM monthly_realization_rows
    WHERE month='2026-01' AND is_return=1 LIMIT 1
""").fetchone()
print((r[0][:500] if r and r[0] else 'нет raw_json'))

con.close()