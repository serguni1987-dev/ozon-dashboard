src = open("sync_pnl.py", encoding="utf-8").read()

old = '''    unit_rows = con.execute("""
        SELECT sku,
               COUNT(DISTINCT unit_number) AS units,
               p.cost_price
        FROM accruals a
        LEFT JOIN products p ON p.sku = a.sku
        WHERE a.date >= ? AND a.date < ?
          AND a.accrued_category = 'POSTING'
          AND a.seller_price IS NOT NULL
          AND a.sku IS NOT NULL
        GROUP BY a.sku
    """, (d1, d2)).fetchall()'''

new = '''    unit_rows = con.execute("""
        SELECT a.sku,
               COUNT(DISTINCT a.unit_number) AS units,
               p.cost_price
        FROM accruals a
        LEFT JOIN products p ON p.sku = a.sku
        WHERE a.date >= ? AND a.date < ?
          AND a.accrued_category = 'POSTING'
          AND a.seller_price IS NOT NULL
          AND a.sku IS NOT NULL
        GROUP BY a.sku
    """, (d1, d2)).fetchall()'''

if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] Исправлено: a.sku и a.unit_number")
else:
    print("[?] Не нашёл блок")
