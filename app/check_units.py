"""
check_units.py - считаем уникальные unit_number в accruals.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("СЧИТАЕМ ЕДИНИЦЫ ПО UNIT_NUMBER")
print("=" * 80)

# 1. За август
print("\n[1] Август — accruals:")
for r in con.execute("""
    SELECT
        COUNT(DISTINCT unit_number) AS units,
        COUNT(*) AS records
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND unit_number IS NOT NULL
"""):
    print(f"    Уникальных unit_number: {r['units']}")
    print(f"    Всего записей:          {r['records']}")

# 2. За сентябрь
print("\n[2] Сентябрь — accruals:")
for r in con.execute("""
    SELECT
        COUNT(DISTINCT unit_number) AS units,
        COUNT(*) AS records
    FROM accruals
    WHERE date >= '2026-09-01' AND date < '2026-10-01'
      AND unit_number IS NOT NULL
"""):
    print(f"    Уникальных unit_number: {r['units']}")
    print(f"    Всего записей:          {r['records']}")

# 3. Сравнение с delivered и realization
print("\n[3] Сравнение с sales_daily и realization:")
print(f"    {'Месяц':<12} {'delivered':>10} {'real.qty':>10}")
print("    " + "-" * 35)

for m in ["2026-06", "2026-07", "2026-08", "2026-09"]:
    y, mm = m.split("-")
    d1 = f"{m}-01"
    ny, nm = (int(y) + 1, 1) if int(mm) == 12 else (int(y), int(mm) + 1)
    d2 = f"{ny}-{nm:02d}-01"

    delivered = con.execute("""
        SELECT SUM(delivered) FROM sales_daily
        WHERE date >= ? AND date < ?
    """, (d1, d2)).fetchone()[0] or 0

    real_qty = con.execute("""
        SELECT SUM(quantity) FROM monthly_realization_rows WHERE month = ?
    """, (m,)).fetchone()[0] or 0

    print(f"    {m:<12} {delivered:>10} {real_qty:>10}")

con.close()
