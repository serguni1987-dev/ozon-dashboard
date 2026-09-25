"""patch_cogs_sign.py — fallback: учитывает знак seller_price.
Продажи (+1) минус возвраты (−1).
"""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

OLD = '''    if cogs == 0:
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

NEW = '''    if cogs == 0:
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
            r = con.execute("SELECT cost_price FROM products WHERE sku = ?", (sku,)).fetchone()
            cost = f(r[0]) if r else 0
            if cost > 0:
                cogs += units * cost
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Fallback с учётом знака seller_price")
elif "SUM(sign) AS units" in src:
    print("[i] Патч уже применён")
else:
    print("[?] Не нашёл блок fallback. Проверь строки 114-130 вручную")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")