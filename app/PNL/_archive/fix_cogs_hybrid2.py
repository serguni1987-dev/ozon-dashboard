src = open("sync_pnl.py", encoding="utf-8").read()

idx1 = src.find("unit_rows = con.execute")
idx2 = src.find("cogs = 0.0")

if idx1 < 0 and idx2 < 0:
    print("[?] Не нашёл блок себестоимости")
    raise SystemExit

start = min(i for i in [idx1, idx2] if i > 0)
end = src.find("revenue = sale_price + bonus", start)
if end < 0:
    raise SystemExit("Не нашёл конец блока")

new_block = '''# === Себестоимость: гибрид ===
    # Если есть sales_daily за месяц — delivered × cost_price (точно)
    # Иначе — unit_number × cost_price из accruals (приблизительно)
    cogs = 0.0

    has_sales = con.execute("""
        SELECT COUNT(*) FROM sales_daily
        WHERE date >= ? AND date < ? AND delivered > 0
    """, (d1, d2)).fetchone()[0]

    if has_sales > 0:
        # Точно: delivered × cost_price
        for row in con.execute("""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ?
            GROUP BY p.sku
        """, (d1, d2)):
            cogs += f(row[0]) * f(row[1])
    else:
        # Приблизительно: unit_number × cost_price из accruals
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

src = src[:start] + new_block + src[end:]
open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] Гибридная формула: delivered где есть, unit_number где нет")
