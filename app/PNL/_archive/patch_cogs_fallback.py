"""patch_cogs_fallback.py — меняет логику себестоимости:
было: if real_skus: sales_daily else: accruals
стало: всегда сначала sales_daily, если 0 → accruals fallback.
"""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

OLD = '''    cogs = 0.0
    real_skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])
    else:
        # Fallback: unit_number × cost для месяцев без sales_daily
        for row in con.execute("""
            SELECT a.sku, COUNT(DISTINCT a.unit_number) AS units, p.cost_price
            FROM accruals a
            LEFT JOIN products p ON p.sku = a.sku
            WHERE a.date >= ? AND a.date < ?
              AND a.accrued_category = 'POSTING'
              AND a.seller_price IS NOT NULL
              AND a.sku IS NOT NULL
            GROUP BY a.sku
        """, (d1, d2)):
            units = int(row[1] or 0)
            cost = f(row[2])
            if units > 0 and cost > 0:
                cogs += units * cost
'''

NEW = '''    cogs = 0.0

    # Основной путь: sales_daily (есть с июня)
    real_skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])

    # Fallback: если sales_daily пусто (янв-май) — через accruals POSTING
    if cogs == 0:
        for row in con.execute("""
            SELECT a.sku, COUNT(DISTINCT a.unit_number) AS units, p.cost_price
            FROM accruals a
            LEFT JOIN products p ON p.sku = a.sku
            WHERE a.date >= ? AND a.date < ?
              AND a.accrued_category = 'POSTING'
              AND a.seller_price IS NOT NULL
              AND a.sku IS NOT NULL
            GROUP BY a.sku
        """, (d1, d2)):
            units = int(row[1] or 0)
            cost = f(row[2])
            if units > 0 and cost > 0:
                cogs += units * cost
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Логика cogs переписана")
elif "if cogs == 0:" in src and "Fallback" in src:
    print("[i] Патч уже применён")
else:
    print("[?] Не нашёл блок. Проверь строки 100-129 вручную")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")