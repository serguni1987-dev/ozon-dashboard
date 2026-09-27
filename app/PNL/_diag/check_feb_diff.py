import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

month = "2026-02"
y, m = month.split("-")
d1 = f"{y}-{m}-01"
d2 = f"{y}-{int(m)+1:02d}-01"
d2_end = "2026-03-01"

def to_f(v):
    try: return float(v or 0)
    except: return 0.0

# real_skus
real = [r[0] for r in c.execute(
    "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,))]

print(f"real_skus за {month}: {len(real)}")
print()

print(f"{'sku':>12} | {'delivered':>9} | {'POSTING':>8} | {'cost':>8}")
print("-" * 50)
total_sales = 0
total_fallback = 0
for sku in real:
    # cost
    r = c.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, d2_end)).fetchone()
    cost = to_f(r[0]) if r else 0

    # sales_daily
    r = c.execute("""
        SELECT SUM(delivered) AS d FROM sales_daily
        WHERE sku = ? AND date >= ? AND date < ?
    """, (sku, d1, d2_end)).fetchone()
    dlv = to_f(r[0]) if r else 0
    total_sales += dlv * cost

    # fallback
    r = c.execute("""
        SELECT SUM(sign) AS units FROM (
            SELECT DISTINCT unit_number,
                   CASE WHEN seller_price > 0 THEN 1
                        WHEN seller_price < 0 THEN -1
                        ELSE 0 END AS sign
            FROM accruals
            WHERE sku = ? AND date >= ? AND date < ?
              AND accrued_category = 'POSTING' AND seller_price IS NOT NULL
        )
    """, (sku, d1, d2_end)).fetchone()
    units = int(r[0] or 0) if r else 0
    total_fallback += units * cost

    mark = ""
    if dlv == 0 and units > 0:
        mark = " ← fallback"
    print(f"{sku:>12} | {dlv:>9.0f} | {units:>8} | {cost:>8.0f}{mark}")

print()
print(f"Если считать только sales_daily: {total_sales:>12,.0f}")
print(f"Если считать только fallback:    {total_fallback:>12,.0f}")
print(f"Разница:                          {total_fallback - total_sales:>12,.0f}")

c.close()