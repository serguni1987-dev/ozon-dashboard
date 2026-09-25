import os, sqlite3
con = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ozon.db"))
con.row_factory = sqlite3.Row

print("=== type_id + type_name за 2026 ===")
q = """
    SELECT type_id, type_name,
           COUNT(*) AS n,
           SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date LIKE '2026-%'
    GROUP BY type_id, type_name
    ORDER BY total DESC
"""
for r in con.execute(q):
    print(f"  id={r['type_id']:>4}  n={r['n']:>5}  sum={r['total']:>14,.2f}  name={r['type_name']!r}")

print()
print("=== type_id + type_name за август 2026 ===")
q2 = """
    SELECT type_id, type_name,
           COUNT(*) AS n,
           SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY type_id, type_name
    ORDER BY total DESC
"""
for r in con.execute(q2):
    print(f"  id={r['type_id']:>4}  n={r['n']:>5}  sum={r['total']:>14,.2f}  name={r['type_name']!r}")