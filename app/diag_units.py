"""
diag_units.py - детальный разбор unit_number.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("РАЗБОР UNIT_NUMBER ЗА АВГУСТ")
print("=" * 80)

# 1. По accrued_category
print("\n[1] unit_number по accrued_category:")
for r in con.execute("""
    SELECT accrued_category,
           COUNT(DISTINCT unit_number) AS units,
           COUNT(*) AS records
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND unit_number IS NOT NULL
    GROUP BY accrued_category
"""):
    print(f"    {r['accrued_category']:<15} units={r['units']:>5}  records={r['records']:>5}")

# 2. POSTING + sku not null
print("\n[2] Уникальные unit_number где accrued_category='POSTING' AND sku IS NOT NULL:")
r = con.execute("""
    SELECT COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND accrued_category = 'POSTING'
      AND sku IS NOT NULL
      AND unit_number IS NOT NULL
""").fetchone()
print(f"    {r['units']}")

# 3. Уникальные unit_number где есть sale_price
print("\n[3] Уникальные unit_number где sale_price IS NOT NULL:")
r = con.execute("""
    SELECT COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND sale_price IS NOT NULL
      AND unit_number IS NOT NULL
""").fetchone()
print(f"    {r['units']}")

# 4. Уникальные unit_number где есть seller_price (комиссия)
print("\n[4] Уникальные unit_number где seller_price IS NOT NULL:")
r = con.execute("""
    SELECT COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND seller_price IS NOT NULL
      AND unit_number IS NOT NULL
""").fetchone()
print(f"    {r['units']}")

# 5. Реальные 28 unit_number из realization
print("\n[5] Реальные 28 отправлений из realization — сколько из них в accruals:")
real_units = con.execute("""
    SELECT DISTINCT unit_number FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND accrued_category = 'POSTING'
      AND seller_price IS NOT NULL
""").fetchall()
print(f"    Найдено в accruals: {len(real_units)}")

# 6. Все POSTING с seller_price — посмотреть
print("\n[6] POSTING с seller_price (первые 10):")
for r in con.execute("""
    SELECT unit_number, sku, seller_price, sale_price, total_amount
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND accrued_category = 'POSTING'
      AND seller_price IS NOT NULL
    LIMIT 10
"""):
    print(f"    {r['unit_number']:<25} sku={r['sku']:<12} seller={r['seller_price']:>8,.0f} "
          f"sale={r['sale_price']:>8,.0f} total={r['total_amount']:>8,.0f}")

con.close()
