from unitka.db import connect

conn = connect()
cur = conn.cursor()

# 1. Выручка (как в дашборде)
cur.execute("SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals WHERE date LIKE '2026-10-%'")
rev = cur.fetchone()[0]

# 2. Расходы Ozon
cur.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions WHERE type = 'deduction' AND date LIKE '2026-10-%'")
exp = cur.fetchone()[0]

# 3. Себестоимость (COGS)
cur.execute("SELECT SUM(quantity) FROM monthly_realization_rows WHERE month = '2026-10' AND is_return = 0")
qty = cur.fetchone()[0] or 0

cur.execute("""
    SELECT SUM(m.quantity * c.cost_price) 
    FROM monthly_realization_rows m
    LEFT JOIN (
        SELECT sku, cost_price FROM product_cost_history 
        WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
    ) c ON m.sku = c.sku
    WHERE m.month = '2026-10' AND m.is_return = 0
""")
cogs = cur.fetchone()[0] or 0.0

print('=== РАСШИФРОВКА ОКТЯБРЯ ===')
print(f'Выручка:         {rev:,.2f} руб.')
print(f'Расходы Ozon:    {exp:,.2f} руб.')
print(f'Кол-во продаж:   {qty} шт.')
print(f'Себестоимость:   {cogs:,.2f} руб.')
print(f'-------------------------')
print(f'Прибыль:         {rev - cogs - exp:,.2f} руб.')
conn.close()