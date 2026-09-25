"""check_costs_alert.py — алерт: SKU из реализации без себестоимости."""
import sqlite3, sys

c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
problems = []

for r in c.execute("""
    SELECT DISTINCT mr.sku, mr.offer_id
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
"""):
    problems.append(f"  БЕЗ COST: sku={r['sku']} offer_id={r['offer_id']}")

for r in c.execute("""
    SELECT DISTINCT mr.sku, mr.offer_id
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.is_own IS NULL OR p.is_own = 0
"""):
    problems.append(f"  БЕЗ is_own=1: sku={r['sku']} offer_id={r['offer_id']}")

for r in c.execute("""
    SELECT DISTINCT mr.sku, mr.offer_id
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.sku IS NULL
"""):
    problems.append(f"  НЕТ в products: sku={r['sku']} offer_id={r['offer_id']}")

c.close()

if problems:
    print("=" * 70)
    print("[!] АЛЕРТ: проблемы с себестоимостью")
    print("=" * 70)
    for p in problems[:30]:
        print(p)
    if len(problems) > 30:
        print(f"  ... и ещё {len(problems) - 30}")
    sys.exit(1)
else:
    print("[OK] Себестоимость в порядке: все SKU из реализации покрыты")
    sys.exit(0)