import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

# Берём RED SKU без продаж за 30 дней + их последний остаток
rows = con.execute("""
    WITH last_stock AS (
        SELECT sku, stock,
               ROW_NUMBER() OVER (PARTITION BY sku ORDER BY date DESC) AS rn
        FROM sales_daily
    )
    SELECT cp.offer_id, p.name, cp.price, cp.min_price,
           ls.stock AS last_stock,
           COALESCE(agg.orders, 0) AS orders_30d
    FROM current_prices cp
    JOIN products p ON p.offer_id = cp.offer_id
    LEFT JOIN last_stock ls ON ls.sku = p.sku AND ls.rn = 1
    LEFT JOIN (
        SELECT sku, SUM(orders_units) AS orders
        FROM sales_daily
        WHERE date >= '2026-08-21'
        GROUP BY sku
    ) agg ON agg.sku = p.sku
    WHERE cp.price_index_color = 'RED'
      AND p.is_own = 1 AND p.is_archived = 0
      AND COALESCE(agg.orders, 0) = 0
""").fetchall()

# Группировка по остатку
zero = [r for r in rows if (r["last_stock"] or 0) == 0]
positive = [r for r in rows if (r["last_stock"] or 0) > 0]
none = [r for r in rows if r["last_stock"] is None]

print(f"RED + без продаж: всего {len(rows)}")
print(f"  Остаток = 0:      {len(zero)}")
print(f"  Остаток > 0:      {len(positive)}")
print(f"  Остаток неизвестен: {len(none)}")

if positive:
    print(f"\nС остатком > 0 (это и есть проблема цены):")
    print(f"  {'Offer ID':<18} {'Цена':>8} {'Min':>8} {'Остаток':>8}")
    print("  " + "-" * 50)
    for r in positive[:20]:
        print(f"  {r['offer_id']:<18} {r['price']:>8,.0f} {r['min_price'] or 0:>8,.0f} {r['last_stock']:>8}")

con.close()
