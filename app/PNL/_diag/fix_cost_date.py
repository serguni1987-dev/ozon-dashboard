import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Эти 13 SKU с cost_price, но без cost_date ===")
for r in c.execute("""
    SELECT sku, offer_id, name, cost_price, is_own
    FROM products
    WHERE cost_price > 0 AND cost_date IS NULL
    ORDER BY offer_id
"""):
    name = (r['name'] or '')[:40]
    print(f"  {r['sku']:>12}  {r['offer_id']:<22}  cost={r['cost_price']}  is_own={r['is_own']}  {name}")

n = c.execute("SELECT COUNT(*) FROM products WHERE cost_price > 0 AND cost_date IS NULL").fetchone()[0]

print(f"\nПроставляю cost_date='2026-01-01' для {n} строк...")
c.execute("""
    UPDATE products
    SET cost_date = '2026-01-01'
    WHERE cost_price > 0 AND cost_date IS NULL
""")
c.commit()

print("\n=== После: актуальность cost_date ===")
for r in c.execute("""
    SELECT cost_date, COUNT(*) AS n FROM products WHERE cost_price > 0
    GROUP BY cost_date ORDER BY cost_date DESC
"""):
    print(f"  {r['cost_date']}  {r['n']}")

c.close()