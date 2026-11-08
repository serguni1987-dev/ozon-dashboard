import sqlite3

con = sqlite3.connect(r'C:\Users\sergu\Desktop\проект\app\ozon.db')

print('=== Возвраты 2026-01 (is_return=1) ===')
print(f'{"sku":>10} {"offer_id":>22} {"qty":>4} {"cost":>8} {"cost*qty":>10}')
total_ret = 0
for r in con.execute("""
    SELECT sku, offer_id, quantity
    FROM monthly_realization_rows
    WHERE month='2026-01' AND is_return=1
    ORDER BY sku
"""):
    sku, offer, qty = r
    c = con.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from<'2026-02-01'
        ORDER BY date_from DESC, id DESC LIMIT 1
    """, (sku,)).fetchone()
    cost = c[0] if c and c[0] else 0
    s = cost * qty
    total_ret += s
    print(f'{sku:>10} {str(offer):>22} {qty:>4} {cost:>8.0f} {s:>10.0f}')
print(f'{"ИТОГО":>10} {"":>22} {"":>4} {"":>8} {total_ret:>10.0f}')

print('\n=== Продажи 2026-01 (is_return=0) по тем же SKU ===')
for r in con.execute("""
    SELECT sku, offer_id, quantity
    FROM monthly_realization_rows
    WHERE month='2026-01' AND is_return=0
      AND sku IN (SELECT sku FROM monthly_realization_rows
                  WHERE month='2026-01' AND is_return=1)
"""):
    print(r)

print('\n=== Проданные SKU (is_return=0) за 2025-12 ===')
for r in con.execute("""
    SELECT sku, offer_id, SUM(quantity)
    FROM monthly_realization_rows
    WHERE month='2025-12' AND is_return=0
      AND sku IN (SELECT sku FROM monthly_realization_rows
                  WHERE month='2026-01' AND is_return=1)
    GROUP BY sku, offer_id
"""):
    print(r)

con.close()