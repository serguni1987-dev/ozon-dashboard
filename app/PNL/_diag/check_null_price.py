import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Апрель: POSTING с seller_price IS NULL ===")
for r in c.execute("""
    SELECT accrual_id, date, sku, unit_number, seller_price, sale_price,
           sale_commission, total_amount
    FROM accruals
    WHERE date >= '2026-04-01' AND date <= '2026-04-30'
      AND accrued_category = 'POSTING'
      AND seller_price IS NULL
    LIMIT 30
"""):
    print(f"  {r['date']}  sku={r['sku']}  unit={r['unit_number']}  "
          f"sp={r['seller_price']}  slp={r['sale_price']}  "
          f"comm={r['sale_commission']}  total={r['total_amount']}")

# Сколько уникальных unit_number
r = c.execute("""
    SELECT COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-04-01' AND date <= '2026-04-30'
      AND accrued_category = 'POSTING'
      AND seller_price IS NULL
      AND unit_number IS NOT NULL
""").fetchone()
print(f"\nУникальных unit_number с null: {r['units']}")

# То же с sku
r = c.execute("""
    SELECT COUNT(DISTINCT sku) AS skus
    FROM accruals
    WHERE date >= '2026-04-01' AND date <= '2026-04-30'
      AND accrued_category = 'POSTING'
      AND seller_price IS NULL
      AND sku IS NOT NULL
""").fetchone()
print(f"Уникальных sku с null: {r['skus']}")

c.close()