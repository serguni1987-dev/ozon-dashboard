import os, sqlite3

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
con = sqlite3.connect(os.path.join(APP_DIR, "ozon.db"))
con.row_factory = sqlite3.Row

print("══ Все type_id за 2026 ═══════════════════════════")
q = """
    SELECT type_id, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date LIKE '2026-%'
    GROUP BY type_id
    ORDER BY total DESC
"""
for r in con.execute(q):
    print(f"  type_id={r['type_id']:>6}  n={r['n']:>5}  sum={r['total']:>14,.2f}")

print()
print("══ За АВГУСТ 2026 ════════════════════════════════")
q2 = """
    SELECT type_id, COUNT(*) AS n, SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY type_id
    ORDER BY total DESC
"""
for r in con.execute(q2):
    print(f"  type_id={r['type_id']:>6}  n={r['n']:>5}  sum={r['total']:>14,.2f}")

print()
print("══ Колонки accruals_services ═════════════════════")
cols = [c[1] for c in con.execute("PRAGMA table_info(accruals_services)")]
print("  ", cols)

print()
print("══ Примеры записей (10 шт) ═══════════════════════")
for r in con.execute("SELECT * FROM accruals_services LIMIT 10"):
    d = dict(r)
    print("  ", {k: d[k] for k in list(d)[:8]})