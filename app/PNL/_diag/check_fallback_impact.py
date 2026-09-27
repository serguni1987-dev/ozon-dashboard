import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

MONTHS = [("2026-01","янв"),("2026-02","фев"),("2026-03","мар"),
          ("2026-04","апр"),("2026-05","май"),("2026-06","июн"),
          ("2026-07","июл"),("2026-08","авг")]

print(f"{'Мес':<5} | {'real':>5} | {'sales':>5} | {'разница':>8} | SKU без sales_daily")
print("-" * 70)

for month, name in MONTHS:
    y, m = month.split("-")
    d1 = f"{y}-{m}-01"
    d2 = f"{int(y)+1}-01-01" if m == "12" else f"{y}-{int(m)+1:02d}-01"

    # SKU из реализации
    real_skus = set(r[0] for r in c.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ? AND sku IS NOT NULL",
        (month,)
    ))

    # SKU из sales_daily с delivered > 0
    sales_skus = set()
    for r in c.execute("""
        SELECT sku, SUM(delivered) AS d
        FROM sales_daily WHERE date >= ? AND date < ?
        GROUP BY sku HAVING SUM(delivered) > 0
    """, (d1, d2)):
        sales_skus.add(r[0])

    diff = real_skus - sales_skus
    # Какие из них имеют accruals.POSTING?
    to_fallback = []
    for sku in diff:
        r = c.execute("""
            SELECT COUNT(DISTINCT unit_number) AS units
            FROM accruals WHERE sku = ? AND date >= ? AND date < ?
              AND accrued_category = 'POSTING' AND seller_price IS NOT NULL
        """, (sku, d1, d2)).fetchone()
        if r and r["units"]:
            to_fallback.append((sku, r["units"]))

    print(f"{name:<5} | {len(real_skus):>5} | {len(sales_skus):>5} | {len(diff):>8} | "
          f"{len(to_fallback)} SKU с POSTING")

    if to_fallback:
        for sku, units in to_fallback[:5]:
            print(f"        sku={sku}  POSTING units={units}")

c.close()