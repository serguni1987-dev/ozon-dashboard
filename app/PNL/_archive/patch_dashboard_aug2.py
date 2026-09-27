src = open("daily_dashboard.py", encoding="utf-8").read()

# 1. block_money — "весь период" → "с 1 августа"
old1 = '''("весь период", con.execute("SELECT MIN(date) FROM sales_daily").fetchone()[0], max_date),'''
new1 = '''("с 1 августа", "2026-08-01", max_date),'''
if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] block_money: 'весь период' → 'с 1 августа'")

# 2. block_result — min_date = MIN(date) → 2026-08-01
old2 = '''    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = con.execute("SELECT MIN(date) FROM sales_daily").fetchone()[0]

    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = comm = serv = profit = 0.0'''
new2 = '''    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = "2026-08-01"  # реальный старт бизнеса

    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = comm = serv = profit = 0.0'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] block_result: MIN(date) → 2026-08-01")
else:
    print("[?] Не нашёл блок в block_result")

open("daily_dashboard.py", "w", encoding="utf-8").write(src)
print("\\nГотово.")
