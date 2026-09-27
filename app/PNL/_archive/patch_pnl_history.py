"""patch_pnl_history.py — sync_pnl.py берёт себестоимость из product_cost_history,
действующую на конец месяца."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

# ── Патч 1: основной путь через sales_daily ──
OLD1 = '''    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])'''

NEW1 = '''    if real_skus:
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
                cogs += cost * f(row[1])'''

if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    print("[OK] Основной путь: цена из истории")
else:
    print("[?] Не нашёл основной путь cogs")

# ── Патч 2: fallback через accruals ──
OLD2 = '''            r = con.execute("SELECT cost_price FROM products WHERE sku = ?", (sku,)).fetchone()
            cost = f(r[0]) if r else 0
            if cost > 0:
                cogs += units * cost'''

NEW2 = '''            r = con.execute("""
                SELECT cost_price FROM product_cost_history
                WHERE sku = ? AND date_from < ?
                ORDER BY date_from DESC LIMIT 1
            """, (sku, d2)).fetchone()
            cost = f(r[0]) if r and r[0] else 0
            if cost > 0:
                cogs += units * cost'''

if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)
    print("[OK] Fallback: цена из истории")
else:
    print("[?] Не нашёл fallback cogs")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] PNL/sync_pnl.py сохранён")