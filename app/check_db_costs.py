import sqlite3, os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

r = con.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN cost_price IS NOT NULL AND cost_price > 0 THEN 1 ELSE 0 END) AS with_cost,
        SUM(CASE WHEN cost_price IS NULL OR cost_price = 0 THEN 1 ELSE 0 END) AS without_cost
    FROM products WHERE is_own = 1
""").fetchone()
print(f"Своих SKU: {r['total']}")
print(f"С себестоимостью: {r['with_cost']}")
print(f"Без себестоимости: {r['without_cost']}")

print(f"\nПримеры (10 с себестоимостью):")
for row in con.execute("""
    SELECT offer_id, name, cost_price FROM products
    WHERE is_own = 1 AND cost_price > 0
    LIMIT 10
"""):
    print(f"  {row['offer_id']:<20} {row['cost_price']:>10,.2f}  {(row['name'] or '')[:50]}")
con.close()
