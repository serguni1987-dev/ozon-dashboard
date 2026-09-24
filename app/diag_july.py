import os, sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

print("=== accruals за 2026-06 / 2026-07 ===")
for r in con.execute("""
    SELECT substr(date,1,7) AS m, COUNT(*) AS n
    FROM accruals
    WHERE date LIKE '2026-06%' OR date LIKE '2026-07%'
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  записей: {r['n']}")
print("  (пусто = ничего не синкано)")

print()
print("=== accruals_services за 2026-06 / 2026-07 ===")
for r in con.execute("""
    SELECT substr(date,1,7) AS m, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date LIKE '2026-06%' OR date LIKE '2026-07%'
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  n={r['n']:>5}  sum={r['total'] or 0:>12,.2f}")

print()
print("=== monthly_realization_rows за июнь/июль ===")
for r in con.execute("""
    SELECT month, COUNT(*) AS n, SUM(sale_price) AS slp, SUM(bonus) AS bonus
    FROM monthly_realization_rows
    WHERE month IN ('2026-06','2026-07')
    GROUP BY month ORDER BY month
"""):
    print(f"  {r['month']}  n={r['n']:>3}  slp={r['slp'] or 0:>12,.2f}  bonus={r['bonus'] or 0:>12,.2f}")

print()
print("=== sales_daily за июнь/июль ===")
for r in con.execute("""
    SELECT substr(date,1,7) AS m, COUNT(*) AS n, SUM(delivered) AS d
    FROM sales_daily
    WHERE date LIKE '2026-06%' OR date LIKE '2026-07%'
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  записей: {r['n']:>5}  delivered: {r['d'] or 0}")

print()
print("=== monthly_reports — какие месяцы синканы ===")
for r in con.execute("SELECT * FROM monthly_reports ORDER BY 1"):
    d = dict(r)
    print("  ", d)