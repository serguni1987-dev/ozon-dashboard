src = open("sync_pnl.py", encoding="utf-8").read()

idx1 = src.find("real_skus = [row[0] for row in con.execute")
idx2 = src.find("cogs = 0.0")

if idx1 < 0 and idx2 < 0:
    print("[?] Не нашёл блок себестоимости")
    raise SystemExit

start = idx1 if idx1 > 0 else idx2
end = src.find("revenue = sale_price + bonus", start)
if end < 0:
    raise SystemExit("Не нашёл конец блока")

new_block = '''# === Себестоимость через unit_number из accruals ===
    # Считаем проданные единицы по каждому SKU и умножаем на cost_price
    cogs = 0.0

    unit_rows = con.execute("""
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
    """, (d1, d2)).fetchall()

    for row in unit_rows:
        units = int(row[1] or 0)
        cost = f(row[2])
        if units > 0 and cost > 0:
            cogs += units * cost

    '''

src = src[:start] + new_block + src[end:]
open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] Себестоимость через unit_number × cost_price")
