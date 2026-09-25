import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== ITEM за январь: примеры ===")
for r in c.execute("""
    SELECT sku, unit_number, seller_price, sale_price, accrued_category
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
      AND accrued_category = 'ITEM'
    LIMIT 8
"""):
    print(f"  sku={r['sku']} unit={r['unit_number']} sp={r['seller_price']} "
          f"slp={r['sale_price']}")

print()
print("=== NON_ITEM за январь: примеры ===")
for r in c.execute("""
    SELECT sku, unit_number, seller_price, sale_price, accrued_category
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
      AND accrued_category = 'NON_ITEM'
    LIMIT 8
"""):
    print(f"  sku={r['sku']} unit={r['unit_number']} sp={r['seller_price']} "
          f"slp={r['sale_price']}")

print()
print("=== Сводка по category за январь ===")
for r in c.execute("""
    SELECT accrued_category,
           COUNT(*) AS n,
           COUNT(DISTINCT sku) AS skus,
           COUNT(DISTINCT unit_number) AS units,
           SUM(CASE WHEN sale_price < 0 THEN 1 ELSE 0 END) AS negative,
           SUM(sale_price) AS total_slp
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
    GROUP BY accrued_category
"""):
    print(f"  {r['accrued_category']:<10} "
          f"n={r['n']:>4} skus={r['skus']:>4} units={r['units']:>4} "
          f"neg={r['negative']:>3} total_slp={r['total_slp'] or 0:>12,.2f}")

print()
print("=== POSTING с отрицательным seller_price (возвраты?) ===")
r = c.execute("""
    SELECT COUNT(*) AS n, COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
      AND accrued_category = 'POSTING'
      AND seller_price < 0
""").fetchone()
print(f"  n={r['n']}  units={r['units']}")

print()
print("=== POSTING: сколько положительных, сколько отрицательных ===")
for r in c.execute("""
    SELECT CASE WHEN seller_price > 0 THEN 'положительный'
                WHEN seller_price < 0 THEN 'отрицательный'
                ELSE 'null' END AS sign,
           COUNT(*) AS n, COUNT(DISTINCT unit_number) AS units
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
      AND accrued_category = 'POSTING'
    GROUP BY sign
"""):
    print(f"  {r['sign']:<18}  n={r['n']:>3}  units={r['units']:>3}")

c.close()