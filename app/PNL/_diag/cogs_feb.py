import sqlite3

con = sqlite3.connect(r'C:\Users\sergu\Desktop\проект\app\ozon.db')

print('=== monthly_realization_rows 2026-02 ===')
for r in con.execute("""
    SELECT is_return, COUNT(*) AS rows, SUM(quantity) AS qty
    FROM monthly_realization_rows
    WHERE month='2026-02'
    GROUP BY is_return
"""):
    print(f'is_return={r[0]}: rows={r[1]}, qty={r[2]}')

def cogs(include_returns):
    total = 0
    if include_returns:
        q = """
            SELECT sku,
                   SUM(CASE WHEN is_return=0 THEN quantity
                            WHEN is_return=1 THEN -quantity END) AS q
            FROM monthly_realization_rows
            WHERE month='2026-02'
            GROUP BY sku
        """
    else:
        q = """
            SELECT sku, SUM(quantity) AS q
            FROM monthly_realization_rows
            WHERE month='2026-02' AND is_return=0
            GROUP BY sku
        """
    for sku, qty in con.execute(q):
        if not qty or qty <= 0:
            continue
        c = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku=? AND date_from<'2026-03-01'
            ORDER BY date_from DESC, id DESC LIMIT 1
        """, (sku,)).fetchone()
        if c and c[0]:
            total += c[0] * qty
    return total

print(f'\nCOGS только выкуп   = {cogs(False):>12,.2f}')
print(f'COGS выкуп−возвраты = {cogs(True):>12,.2f}')
print(f'Наш P&L (Sheets)    = {111458:>12,.2f}')
print(f'Цель (Точка)        = {104799:>12,.2f}')

# ---- Без фильтра quantity>0, чтобы увидеть весь список возвратов
print('\n=== Возвраты февраля построчно ===')
total_ret = 0
for r in con.execute("""
    SELECT sku, offer_id, quantity
    FROM monthly_realization_rows
    WHERE month='2026-02' AND is_return=1
    ORDER BY sku
"""):
    sku, offer, qty = r
    c = con.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from<'2026-03-01'
        ORDER BY date_from DESC, id DESC LIMIT 1
    """, (sku,)).fetchone()
    cost = c[0] if c and c[0] else 0
    s = cost * qty
    total_ret += s
    print(f'{sku:>10} {str(offer):>22} {qty:>4} {cost:>8.0f} {s:>10.0f}')
print(f'{"ИТОГО":>10} {"":>22} {"":>4} {"":>8} {total_ret:>10.0f}')

con.close()