import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Продажи OCE013E4 (sku=1605108599) по месяцам ===")
for r in c.execute("""
    SELECT month, SUM(quantity) AS qty, SUM(sale_price) AS slp
    FROM monthly_realization_rows
    WHERE offer_id = 'OCE013E4'
    GROUP BY month ORDER BY month
"""):
    print(f"  {r['month']}  qty={r['qty']}  slp={r['slp']:,.2f}")

print()
print("=== В sales_daily по месяцам ===")
for r in c.execute("""
    SELECT substr(date,1,7) AS m, SUM(delivered) AS d, SUM(revenue) AS rev
    FROM sales_daily WHERE sku = 1605108599
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  delivered={r['d']}  revenue={r['rev']:,.2f}")

print()
print("=== В accruals POSTING (fallback) по месяцам ===")
for r in c.execute("""
    SELECT substr(date,1,7) AS m, COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE sku = 1605108599 AND accrued_category = 'POSTING'
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  units={r['units']}")

c.close()