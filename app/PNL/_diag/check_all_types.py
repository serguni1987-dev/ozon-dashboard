import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "PNL"))
import sync_pnl

c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
known = set(sync_pnl.CATEGORY_MAP.keys())
ph = ",".join("?" * len(known))

print("=== Vse type_id vne CATEGORY_MAP (za 2026) ===")
rows = c.execute(f"""
    SELECT type_id, type_name, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE type_id NOT IN ({ph})
      AND date >= '2026-01-01'
    GROUP BY type_id, type_name
    ORDER BY total DESC
""", tuple(known)).fetchall()

if not rows:
    print("  (net - vse type_id razmecheny)")
else:
    for r in rows:
        print(f"  id={r['type_id']:>4}  n={r['n']:>4}  sum={r['total']:>12,.2f}  {r['type_name']!r}")

c.close()
