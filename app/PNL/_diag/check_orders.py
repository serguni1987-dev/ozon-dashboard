# -*- coding: utf-8 -*-
import sqlite3
DB = r"C:\Users\sergu\Desktop\проект\app\ozon.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("Колонки orders_created:")
for r in c.execute("PRAGMA table_info(orders_created)"):
    print(f"  {r['name']}  {r['type']}")

print("\nАгрегат по created_at >= 2026-08-01:")
q = """
SELECT strftime('%Y-%m', created_at) AS m,
       status,
       scheme,
       COUNT(*) AS n
FROM orders_created
WHERE created_at >= '2026-08-01'
GROUP BY m, status, scheme
ORDER BY m, status, scheme
"""
for r in c.execute(q):
    print(f"  {r['m']}  status={r['status']:<12} scheme={r['scheme']}  n={r['n']}")

print("\nИтог по месяцам (delivered / cancelled / delivering):")
q2 = """
SELECT strftime('%Y-%m', created_at) AS m, status, COUNT(*) AS n
FROM orders_created
WHERE created_at >= '2026-07-01'
GROUP BY m, status
ORDER BY m, status
"""
for r in c.execute(q2):
    print(f"  {r['m']}  {r['status']:<12}  {r['n']}")

c.close()