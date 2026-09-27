import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

c.execute("""
    UPDATE products SET cost_price = 5337, cost_date = '2026-01-01'
    WHERE offer_id = 'OCE013E4'
""")
c.execute("""
    DELETE FROM product_cost_history
    WHERE sku = (SELECT sku FROM products WHERE offer_id = 'OCE013E4')
      AND date_from = '2026-08-01'
""")
c.commit()

print("=== История OCE013E4 после отката ===")
for r in c.execute("""
    SELECT date_from, cost_price, source FROM product_cost_history
    WHERE sku = (SELECT sku FROM products WHERE offer_id = 'OCE013E4')
    ORDER BY date_from
"""):
    print(f"  {r['date_from']}  {r['cost_price']}  {r['source']}")

r = c.execute("SELECT cost_price, cost_date FROM products WHERE offer_id = 'OCE013E4'").fetchone()
print(f"products: cost_price={r['cost_price']}  cost_date={r['cost_date']}")
c.close()