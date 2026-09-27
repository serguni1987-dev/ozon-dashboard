"""patch_fallback_per_sku.py — fallback на уровне КАЖДОГО SKU:
если в sales_daily delivered=0, берём units из accruals.POSTING.
"""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

OLD = '''    # Основной путь: sales_daily (есть с июня)
    real_skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT
                (SELECT cost_price FROM product_cost_history
                 WHERE sku = sd.sku AND date_from < ?
                 ORDER BY date_from DESC LIMIT 1) AS cost_price,
                SUM(sd.delivered) AS d
            FROM sales_daily sd
            WHERE sd.date >= ? AND sd.date < ? AND sd.sku IN ({q})
            GROUP BY sd.sku
        """, (d2, d1, d2, *real_skus)):
            cost = f(row[0]) if row[0] is not None else 0
            if cost > 0:
                cogs += cost * f(row[1])

    # Fallback: если sales_daily пусто (янв-май) — через accruals POSTING
    if cogs == 0:
        # Fallback: каждый unit_number — +1 если продажа, -1 если возврат
        for row in con.execute("""
            SELECT sku, SUM(sign) AS units
            FROM (
                SELECT DISTINCT a.sku, a.unit_number,
                       CASE WHEN a.seller_price > 0 THEN 1
                            WHEN a.seller_price < 0 THEN -1
                            ELSE 0 END AS sign
                FROM accruals a
                WHERE a.date >= ? AND a.date < ?
                  AND a.accrued_category = 'POSTING'
                  AND a.seller_price IS NOT NULL
                  AND a.sku IS NOT NULL
            )
            GROUP BY sku
        """, (d1, d2)):
            sku = row[0]
            units = int(row[1] or 0)
            if units == 0:
                continue
            r = con.execute("""
                SELECT cost_price FROM product_cost_history
                WHERE sku = ? AND date_from < ?
                ORDER BY date_from DESC LIMIT 1
            """, (sku, d2)).fetchone()
            cost = f(r[0]) if r and r[0] else 0
            if cost > 0:
                cogs += units * cost
'''

NEW = '''    # Себестоимость per-SKU: sales_daily → fallback accruals.POSTING
    real_skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]

    for sku in real_skus:
        # Цена из истории на конец месяца
        r = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku = ? AND date_from < ?
            ORDER BY date_from DESC LIMIT 1
        """, (sku, d2)).fetchone()
        cost = f(r[0]) if r and r[0] else 0
        if cost == 0:
            continue

        # Основной путь: sales_daily
        r = con.execute("""
            SELECT SUM(delivered) AS d
            FROM sales_daily
            WHERE sku = ? AND date >= ? AND date < ?
        """, (sku, d1, d2)).fetchone()
        delivered = f(r[0]) if r and r[0] else 0

        if delivered > 0:
            cogs += cost * delivered
            continue

        # Fallback: accruals.POSTING (продажи минус возвраты)
        r = con.execute("""
            SELECT SUM(sign) AS units
            FROM (
                SELECT DISTINCT a.unit_number,
                       CASE WHEN a.seller_price > 0 THEN 1
                            WHEN a.seller_price < 0 THEN -1
                            ELSE 0 END AS sign
                FROM accruals a
                WHERE a.sku = ? AND a.date >= ? AND a.date < ?
                  AND a.accrued_category = 'POSTING'
                  AND a.seller_price IS NOT NULL
            )
        """, (sku, d1, d2)).fetchone()
        units = int(r[0] or 0) if r else 0
        if units > 0:
            cogs += cost * units
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] fallback переписан на per-SKU")
    open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] PNL/sync_pnl.py сохранён")
else:
    print("[?] Не нашёл блок cogs — проверь вручную")