import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== История OCE013E4 ===")
for r in c.execute("""
    SELECT date_from, cost_price, source, created_at
    FROM product_cost_history
    WHERE sku = (SELECT sku FROM products WHERE offer_id = 'OCE013E4')
    ORDER BY date_from
"""):
    print(f"  {r['date_from']}  {r['cost_price']:>8.2f}  {r['source']:<12}  {r['created_at']}")

print()
r = c.execute("SELECT cost_price, cost_date FROM products WHERE offer_id = 'OCE013E4'").fetchone()
print(f"products: cost_price={r['cost_price']}  cost_date={r['cost_date']}")

c.close()