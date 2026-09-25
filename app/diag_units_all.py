"""
diag_units_all.py - единицы за все месяцы из accruals.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ЕДИНИЦЫ ПО МЕСЯЦАМ (POSTING + seller_price)")
print("=" * 80)

print()
print(f"{'Месяц':<12} {'accruals':>10} {'delivered':>10} {'real.qty':>10}")
print("-" * 45)

months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09"]

for m in months:
    y, mm = m.split("-")
    d1 = f"{m}-01"
    ny, nm = (int(y) + 1, 1) if int(mm) == 12 else (int(y), int(mm) + 1)
    d2 = f"{ny}-{nm:02d}-01"

    acc = con.execute("""
        SELECT COUNT(DISTINCT unit_number) AS u
        FROM accruals
        WHERE date >= ? AND date < ?
          AND accrued_category = 'POSTING'
          AND seller_price IS NOT NULL
          AND sku IS NOT NULL
    """, (d1, d2)).fetchone()["u"]

    deliv = con.execute("""
        SELECT SUM(delivered) FROM sales_daily
        WHERE date >= ? AND date < ?
    """, (d1, d2)).fetchone()[0] or 0

    rq = con.execute("""
        SELECT SUM(quantity) FROM monthly_realization_rows WHERE month = ?
    """, (m,)).fetchone()[0] or 0

    print(f"{m:<12} {acc:>10} {deliv:>10} {rq:>10}")

print()
print("=" * 80)
print("ЧТО ЕСТЬ В ACCRUALS ПО ДАТАМ")
print("=" * 80)
for r in con.execute("""
    SELECT substr(date, 1, 7) AS m,
           COUNT(DISTINCT unit_number) AS units,
           COUNT(*) AS records
    FROM accruals
    WHERE unit_number IS NOT NULL
    GROUP BY m
    ORDER BY m
"""):
    print(f"  {r['m']}  units={r['units']:>5}  records={r['records']:>5}")

con.close()
