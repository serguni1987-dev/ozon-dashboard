import sqlite3

con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

OZON = {
    "2026-01": 147966, "2026-02": 104799, "2026-03": 44239,
    "2026-04": 28084,  "2026-05": 30861,  "2026-06": 6302,
    "2026-07": None,   "2026-08": 112905,
}

def cost_on(sku, date_end):
    r = con.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, date_end)).fetchone()
    return float(r[0]) if r and r[0] else 0.0

print(f"{'Мес':<10} | {'qty':>5} | {'COGS(real*cost)':>16} | {'Ozon':>12} | {'delta':>10} | {'delta%':>7}")
print("-" * 80)

for month, ozon_val in OZON.items():
    y, m = month.split("-")
    ny, nm = (int(y) + 1, 1) if m == "12" else (int(y), int(m) + 1)
    d2 = f"{ny}-{nm:02d}-01"

    total_qty = 0
    cogs = 0.0
    for r in con.execute("""
        SELECT sku, quantity FROM monthly_realization_rows
        WHERE month = ? AND quantity > 0
    """, (month,)):
        c = cost_on(r["sku"], d2)
        if c == 0:
            continue
        q = r["quantity"]
        total_qty += q
        cogs += c * q

    oz_s = f"{ozon_val:>12,.0f}" if ozon_val else f"{'---':>12}"
    if ozon_val:
        d = cogs - ozon_val
        pct = d / ozon_val * 100
        mark = "OK" if abs(pct) < 2 else "!!"
        print(f"{month:<10} | {total_qty:>5} | {cogs:>16,.2f} | {oz_s} | {d:>+10,.0f} | {pct:>+6.2f}% {mark}")
    else:
        print(f"{month:<10} | {total_qty:>5} | {cogs:>16,.2f} | {oz_s}")

con.close()
