src = open("sync_pnl.py", encoding="utf-8").read()

old = '''    real_skus = [row[0] for row in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    cogs = 0.0
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])'''

new = '''    real_skus = [row[0] for row in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    cogs = 0.0

    if real_skus:
        # Для месяцев с realization — только SKU из отчёта
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])
    else:
        # Fallback для месяцев без realization — все SKU с delivered
        for row in con.execute("""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ?
            GROUP BY p.sku
        """, (d1, d2)):
            cogs += f(row[0]) * f(row[1])'''

if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] Fallback для себестоимости добавлен")
else:
    print("[?] Не нашёл блок себестоимости")
