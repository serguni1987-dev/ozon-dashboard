src = open("sync_pnl.py", encoding="utf-8").read()

idx1 = src.find("real_skus = [row[0] for row in con.execute")
idx2 = src.find("cogs = 0.0")

if idx1 < 0 and idx2 < 0:
    print("[?] Не нашёл блок себестоимости")
    raise SystemExit

start = idx1 if idx1 > 0 else idx2
end = src.find("revenue = sale_price + bonus", start)
if end < 0:
    print("[?] Не нашёл конец блока")
    raise SystemExit

new_block = '''# === Себестоимость через realization.quantity × cost_price ===
    real_rows = con.execute("""
        SELECT r.quantity, p.cost_price
        FROM monthly_realization_rows r
        LEFT JOIN products p ON p.sku = r.sku
        WHERE r.month = ?
    """, (month,)).fetchall()

    cogs = 0.0
    if real_rows:
        for row in real_rows:
            qty = int(row[0] or 0)
            cost = f(row[1])
            if qty > 0 and cost > 0:
                cogs += cost * qty
    else:
        for row in con.execute("""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ?
            GROUP BY p.sku
        """, (d1, d2)):
            cogs += f(row[0]) * f(row[1])

    '''

src = src[:start] + new_block + src[end:]
open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] Формула себестоимости: realization.quantity × cost_price")
