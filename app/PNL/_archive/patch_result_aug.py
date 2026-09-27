src = open("sheets_sync.py", encoding="utf-8").read()

# В build_result — считаем только с 1 августа
src = src.replace(
    '''    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
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
    """, (min_date, max_date)).fetchall()''',
    '''    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
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
    """, (min_date, max_date)).fetchall()'''
)

# Строка подзаголовка
src = src.replace(
    '        [f"период {min_date} — {max_date}", "", "", ""],',
    '        [f"период с 1 августа по {max_date}  (реальный старт бизнеса)", "", "", ""],'
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] РЕЗУЛЬТАТ теперь считает с 1 августа — как ДЕНЬГИ")
