import sqlite3

con = sqlite3.connect(r'C:\Users\sergu\Desktop\проект\app\ozon.db')

print('=== 1. monthly_realization_rows 2026-01 ===')
for r in con.execute("""
    SELECT is_return, COUNT(*) AS rows, SUM(quantity) AS qty
    FROM monthly_realization_rows
    WHERE month = '2026-01'
    GROUP BY is_return
"""):
    print(f'is_return={r[0]}: rows={r[1]}, qty={r[2]}')

def cogs(include_returns: bool):
    total = 0
    if include_returns:
        q = """
            SELECT sku,
                   SUM(CASE WHEN is_return=0 THEN quantity
                            WHEN is_return=1 THEN -quantity END) AS q
            FROM monthly_realization_rows
            WHERE month='2026-01'
            GROUP BY sku
        """
    else:
        q = """
            SELECT sku, SUM(quantity) AS q
            FROM monthly_realization_rows
            WHERE month='2026-01' AND is_return=0
            GROUP BY sku
        """
    for sku, qty in con.execute(q):
        if not qty or qty <= 0:
            continue
        c = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku=? AND date_from<'2026-02-01'
            ORDER BY date_from DESC, id DESC LIMIT 1
        """, (sku,)).fetchone()
        if c and c[0]:
            total += c[0] * qty
    return total

print(f'\nCOGS только выкуп   = {cogs(False):>12,.2f}')
print(f'COGS выкуп−возвраты = {cogs(True):>12,.2f}')
print(f'\nЦель (Точка)        = {147966:>12,.2f}')
print(f'Наш текущий P&L     = {151237:>12,.2f}')

con.close()