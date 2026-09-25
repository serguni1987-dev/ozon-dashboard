"""
diag_services_jan.py - какие услуги загружены за январь.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("УСЛУГИ ЗА ЯНВАРЬ 2026")
print("=" * 80)

print()
print(f"{'type_id':<8} {'Название':<40} {'Сумма':>14} {'Записей':>8}")
print("-" * 75)

total = 0
for r in con.execute("""
    SELECT type_id, type_name,
           SUM(amount) AS total,
           COUNT(*) AS n
    FROM accruals_services
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
    GROUP BY type_id, type_name
    ORDER BY ABS(SUM(amount)) DESC
"""):
    print(f"{r['type_id']:<8} {r['type_name']:<40} {r['total']:>14,.2f} {r['n']:>8}")
    total += abs(r['total'])

print("-" * 75)
print(f"{'ИТОГО':<49} {total:>14,.2f}")

print()
print("=" * 80)
print("СРАВНЕНИЕ: ЯНВАРЬ vs АВГУСТ")
print("=" * 80)

for m, label in [("2026-01", "Январь"), ("2026-08", "Август")]:
    y, mm = m.split("-")
    d1 = f"{m}-01"
    ny, nm = (int(y) + 1, 1) if int(mm) == 12 else (int(y), int(mm) + 1)
    d2 = f"{ny}-{nm:02d}-01"

    total = con.execute("""
        SELECT SUM(amount) AS t FROM accruals_services
        WHERE date >= ? AND date < ?
    """, (d1, d2)).fetchone()["t"] or 0

    # Главные категории
    logistic = con.execute("""
        SELECT SUM(amount) AS t FROM accruals_services
        WHERE date >= ? AND date < ? AND type_id = 32
    """, (d1, d2)).fetchone()["t"] or 0

    print(f"\n  {label}:")
    print(f"    Всего услуг:    {total:>14,.2f}")
    print(f"    Logistic:       {logistic:>14,.2f}")

con.close()
