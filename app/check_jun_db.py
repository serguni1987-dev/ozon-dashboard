import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== accruals_services за 2026-06 ===")
for r in c.execute("""
    SELECT type_id, type_name, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date >= '2026-06-01' AND date < '2026-07-01'
    GROUP BY type_id, type_name
    ORDER BY total DESC
"""):
    print(f"  id={r['type_id']:>4}  n={r['n']:>3}  sum={r['total']:>12,.2f}  {r['type_name']!r}")

print()
print("=== Уникальные даты за июнь ===")
for r in c.execute("""
    SELECT DISTINCT date FROM accruals_services
    WHERE date >= '2026-06-01' AND date < '2026-07-01'
    ORDER BY date
"""):
    print(f"  {r['date']}")

print()
print("=== Есть ли type_id=25 ItemCompensation? ===")
for r in c.execute("""
    SELECT date, sku, type_id, type_name, amount
    FROM accruals_services
    WHERE type_id = 25
"""):
    print(f"  {r['date']}  sku={r['sku']}  sum={r['amount']}")