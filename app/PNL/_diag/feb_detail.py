import sqlite3
import pandas as pd

DB = r'C:\Users\sergu\Desktop\проект\app\ozon.db'

conn = sqlite3.connect(DB)

print('=== Февраль 2026: все продажи (is_return=0) по SKU ===')
print(f'{"sku":>12} {"offer":>22} {"qty":>5} {"cost":>8} {"sum":>10}')

total_buy = 0
rows = []
for sku, offer, qty in conn.execute("""
    SELECT sku, offer_id, SUM(quantity) AS q
    FROM monthly_realization_rows
    WHERE month='2026-02' AND is_return=0
    GROUP BY sku, offer_id
    ORDER BY sku
"""):
    r = conn.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from<'2026-03-01'
        ORDER BY date_from DESC, id DESC LIMIT 1
    """, (sku,)).fetchone()
    cost = r[0] if r and r[0] else 0
    s = cost * qty
    total_buy += s
    rows.append((sku, offer, qty, cost, s))
    print(f'{sku:>12} {str(offer):>22} {qty:>5} {cost:>8.0f} {s:>10.0f}')

print(f'{"ИТОГО выкуп":>12} {"":>22} {"":>5} {"":>8} {total_buy:>10.0f}')

print('\n=== Февраль: возвраты ===')
total_ret = 0
for sku, offer, qty in conn.execute("""
    SELECT sku, offer_id, quantity
    FROM monthly_realization_rows
    WHERE month='2026-02' AND is_return=1
"""):
    r = conn.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from<'2026-03-01'
        ORDER BY date_from DESC, id DESC LIMIT 1
    """, (sku,)).fetchone()
    cost = r[0] if r and r[0] else 0
    s = cost * qty
    total_ret += s
    print(f'{sku:>12} {str(offer):>22} {qty:>5} {cost:>8.0f} {s:>10.0f}')
print(f'{"ИТОГО возвр":>12} {"":>22} {"":>5} {"":>8} {total_ret:>10.0f}')

print(f'\nИтог февраля (выкуп − возвраты) = {total_buy - total_ret:>10.0f}')
print(f'Наш P&L:    111 458')
print(f'Точка:      104 799')
print(f'Δ (наш−Точка) = {111458 - 104799}')

print('\n=== ТОП-10 SKU по вкладу в COGS февраля ===')
top = sorted(rows, key=lambda x: -x[4])[:10]
for sku, offer, qty, cost, s in top:
    print(f'{sku:>12} {str(offer):>22} qty={qty:>3} cost={cost:>7.0f} sum={s:>9.0f}')

conn.close()