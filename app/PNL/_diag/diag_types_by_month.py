import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
for month in ("2026-01", "2026-02", "2026-03", "2026-04", "2026-05"):
    print(f"\n=== {month} ===")
    for r in c.execute("""
        SELECT type_id, type_name, COUNT(*) AS n, SUM(ABS(amount)) AS total
        FROM accruals_services
        WHERE date >= ? AND date <= ?
        GROUP BY type_id, type_name ORDER BY total DESC
    """, (f"{month}-01", f"{month}-31")):
        print(f"  id={r['type_id']:>4}  n={r['n']:>4}  sum={r['total']:>12,.2f}  {r['type_name']!r}")
c.close()
