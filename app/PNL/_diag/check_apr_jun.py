import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

for month, name in [("2026-04","Апрель"), ("2026-06","Июнь")]:
    print(f"=== {name} ({month}) ===")
    r = c.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN seller_price > 0 THEN 1 ELSE 0 END) AS pos,
            SUM(CASE WHEN seller_price < 0 THEN 1 ELSE 0 END) AS neg,
            SUM(CASE WHEN seller_price IS NULL THEN 1 ELSE 0 END) AS nulls,
            SUM(CASE WHEN sku IS NULL THEN 1 ELSE 0 END) AS no_sku
        FROM accruals
        WHERE date >= ? AND date <= ?
          AND accrued_category = 'POSTING'
    """, (f"{month}-01", f"{month}-31")).fetchone()
    for k in r.keys():
        print(f"  {k}: {r[k]}")

    # sales_daily за месяц?
    s = c.execute("""
        SELECT COUNT(*) AS n, SUM(delivered) AS dlv
        FROM sales_daily WHERE date >= ? AND date <= ?
    """, (f"{month}-01", f"{month}-31")).fetchone()
    print(f"  sales_daily: n={s['n']} delivered={s['dlv']}")
    print()