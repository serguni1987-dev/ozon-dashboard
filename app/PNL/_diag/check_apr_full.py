import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Все POSTING за апрель, сгруппированы по unit_number ===")
print(f"{'unit_number':<28} | {'sku':>12} | {'sp':>8} | {'total':>10} | записей")
print("-" * 90)

for r in c.execute("""
    SELECT unit_number, sku,
           MAX(seller_price) AS sp,
           COUNT(*) AS n,
           SUM(total_amount) AS total,
           MIN(date) AS d1, MAX(date) AS d2
    FROM accruals
    WHERE date >= '2026-04-01' AND date <= '2026-04-30'
      AND accrued_category = 'POSTING'
    GROUP BY unit_number
    ORDER BY sp IS NULL, unit_number
"""):
    sp = r['sp'] if r['sp'] is not None else 'NULL'
    print(f"{str(r['unit_number']):<28} | {str(r['sku']):>12} | {str(sp):>8} | "
          f"{r['total']:>10,.2f} | {r['n']}")

# Сводка
print()
r = c.execute("""
    SELECT
        COUNT(DISTINCT unit_number) AS units_total,
        COUNT(DISTINCT CASE WHEN seller_price IS NOT NULL THEN unit_number END) AS units_with_sp,
        COUNT(DISTINCT CASE WHEN seller_price IS NULL THEN unit_number END) AS units_no_sp
    FROM accruals
    WHERE date >= '2026-04-01' AND date <= '2026-04-30'
      AND accrued_category = 'POSTING'
""").fetchone()
print(f"Всего unit_number:               {r['units_total']}")
print(f"С seller_price:                  {r['units_with_sp']}")
print(f"Без seller_price (null):         {r['units_no_sp']}")

# Проверка: сколько из 9 null-unit есть в realization_rows
print()
print("=== Null-unit SKU: есть ли в monthly_realization_rows за апрель? ===")
for r in c.execute("""
    SELECT DISTINCT a.sku
    FROM accruals a
    WHERE a.date >= '2026-04-01' AND a.date <= '2026-04-30'
      AND a.accrued_category = 'POSTING'
      AND a.seller_price IS NULL
      AND a.sku IS NOT NULL
"""):
    sku = r['sku']
    found = c.execute("""
        SELECT 1 FROM monthly_realization_rows
        WHERE month = '2026-04' AND sku = ?
    """, (sku,)).fetchone()
    print(f"  sku={sku}  в realization: {'ДА' if found else 'НЕТ'}")

c.close()