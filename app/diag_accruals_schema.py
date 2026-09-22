"""
diag_accruals_schema.py
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)

print("=" * 80)
print("СХЕМА accruals")
print("=" * 80)
for r in con.execute("PRAGMA table_info(accruals)"):
    print(f"  {r[1]:<25} {r[2]}")

print("\n" + "=" * 80)
print("СХЕМА accruals_services")
print("=" * 80)
for r in con.execute("PRAGMA table_info(accruals_services)"):
    print(f"  {r[1]:<25} {r[2]}")

# Сколько записей и какие поля
print("\n" + "=" * 80)
print("ПРИМЕР ЗАПИСИ ИЗ accruals (август)")
print("=" * 80)
con.row_factory = sqlite3.Row
r = con.execute("""
    SELECT * FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    LIMIT 3
""").fetchall()
for row in r:
    print()
    for k in row.keys():
        print(f"  {k:<25} {row[k]}")

# Все колонки + суммы — какие типы услуг есть
print("\n" + "=" * 80)
print("ACC RUALS_ SERVICES — все type_id за август")
print("=" * 80)
for row in con.execute("""
    SELECT type_id, type_name, SUM(amount) AS total, COUNT(*) AS n
    FROM accruals_services
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY type_id, type_name
    ORDER BY ABS(SUM(amount)) DESC
"""):
    print(f"  {row['type_id']:<5} {row['type_name']:<40} {row['total']:>12,.2f} ({row['n']})")

con.close()
