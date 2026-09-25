import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== accruals_services за 2026-05 ===")
for r in c.execute("""
    SELECT type_id, type_name, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date >= '2026-05-01' AND date <= '2026-05-31'
    GROUP BY type_id, type_name
    ORDER BY total DESC
"""):
    print(f"  id={r['type_id']:>4}  n={r['n']:>3}  sum={r['total']:>12,.2f}  {r['type_name']!r}")

print()
print("=== monthly_realization_rows за май ===")
r = c.execute("""
    SELECT SUM(sale_price) AS slp, SUM(bonus) AS bns,
           SUM(coinvestment) AS ci, SUM(gross_commission) AS comm
    FROM monthly_realization_rows WHERE month = '2026-05'
""").fetchone()
print(f"  sale_price:      {r['slp'] or 0:>14,.2f}")
print(f"  bonus:           {r['bns'] or 0:>14,.2f}")
print(f"  coinvestment:    {r['ci'] or 0:>14,.2f}")
print(f"  gross_comm:      {r['comm'] or 0:>14,.2f}")