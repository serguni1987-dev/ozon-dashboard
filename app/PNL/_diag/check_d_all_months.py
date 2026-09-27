import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

OZON = {
    "2026-01": 147966, "2026-02": 104799, "2026-03": 44239,
    "2026-04": 28084, "2026-05": 30861, "2026-06": 6302,
    "2026-08": 112905,
}

def to_f(v):
    try: return float(v or 0)
    except: return 0.0

def get_cost(sku, month):
    y, m = month.split("-")
    d2 = f"{y}-{int(m)+1:02d}-01" if m != "12" else f"{int(y)+1}-01-01"
    r = c.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, d2)).fetchone()
    return to_f(r[0]) if r else 0

print(f"{'Мес':<6} | {'Ozon':>8} | {'D (qty×cost)':>12} | {'Δ':>8} | {'Δ%':>6}")
print("-" * 55)

for month, ozon in OZON.items():
    total = 0
    for r in c.execute("""
        SELECT sku, SUM(quantity) AS q
        FROM monthly_realization_rows
        WHERE month = ? AND sku IS NOT NULL
        GROUP BY sku
    """, (month,)):
        cost = get_cost(r["sku"], month)
        q = int(r["q"] or 0)
        if cost > 0 and q != 0:
            total += cost * q

    diff = total - ozon
    pct = (diff / ozon * 100) if ozon else 0
    mark = "✓" if abs(pct) < 5 else "⚠"
    print(f"{month:<6} | {ozon:>8,} | {total:>12,.0f} | {diff:>+8,.0f} | {pct:>+5.1f}% {mark}")

c.close()