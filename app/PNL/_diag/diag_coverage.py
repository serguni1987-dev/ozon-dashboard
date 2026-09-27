"""
diag_coverage.py — сравнивает sales_daily и accruals по дням и SKU.
"""
import sqlite3

DB = "ozon.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 100)
print("ПОКРЫТИЕ: sales_daily vs accruals")
print("=" * 100)

print("\n[1] По дням:")
print(f"  {'Дата':<12} {'sales.revenue':>14} {'accruals.sale':>14} {'accruals.seller':>16} {'заказов':>8}")
print("  " + "-" * 70)

daily = con.execute("""
    WITH sd AS (
        SELECT date, SUM(revenue) AS rev, SUM(orders_units) AS orders
        FROM sales_daily GROUP BY date
    ),
    ac AS (
        SELECT date, SUM(sale_price) AS slp, SUM(seller_price) AS sp
        FROM accruals GROUP BY date
    )
    SELECT COALESCE(sd.date, ac.date) AS date,
           COALESCE(sd.rev, 0) AS rev,
           COALESCE(sd.orders, 0) AS orders,
           COALESCE(ac.slp, 0) AS slp,
           COALESCE(ac.sp, 0) AS sp
    FROM sd LEFT JOIN ac ON sd.date = ac.date
    UNION
    SELECT COALESCE(sd.date, ac.date),
           COALESCE(sd.rev, 0),
           COALESCE(sd.orders, 0),
           COALESCE(ac.slp, 0),
           COALESCE(ac.sp, 0)
    FROM ac LEFT JOIN sd ON sd.date = ac.date
    WHERE sd.date IS NULL
    ORDER BY date
""").fetchall()

for r in daily:
    print(f"  {r['date']:<12} {r['rev']:>14,.0f} {r['slp']:>14,.0f} {r['sp']:>16,.0f} {r['orders']:>8}")

# Итоги
tot = con.execute("""
    SELECT (SELECT SUM(revenue) FROM sales_daily) AS rev,
           (SELECT SUM(orders_units) FROM sales_daily) AS orders,
           (SELECT SUM(sale_price) FROM accruals) AS slp,
           (SELECT SUM(seller_price) FROM accruals) AS sp
""").fetchone()
print(f"\n  {'ИТОГО':<12} {tot['rev']:>14,.0f} {tot['slp']:>14,.0f} {tot['sp']:>16,.0f} {tot['orders']:>8}")

# 2. Совпадение по SKU
print("\n[2] Пересечение по SKU:")
common = con.execute("""
    SELECT COUNT(DISTINCT a.sku) FROM accruals a
    WHERE a.sku IN (SELECT sku FROM sales_daily WHERE orders_units > 0)
""").fetchone()[0]
only_accr = con.execute("""
    SELECT COUNT(DISTINCT a.sku) FROM accruals a
    WHERE a.sku NOT IN (SELECT sku FROM sales_daily WHERE orders_units > 0)
""").fetchone()[0]
only_sales = con.execute("""
    SELECT COUNT(DISTINCT s.sku) FROM sales_daily s
    WHERE s.orders_units > 0
      AND s.sku NOT IN (SELECT sku FROM accruals WHERE sku IS NOT NULL)
""").fetchone()[0]
print(f"  SKU есть в обоих источниках: {common}")
print(f"  Только в accruals:           {only_accr}")
print(f"  Только в sales_daily:        {only_sales}")

# 3. Топ-10 SKU с продажами, но без accruals
print("\n[3] SKU с продажами, но без accruals (топ-10 по выручке):")
rows = con.execute("""
    SELECT p.offer_id, p.name, SUM(sd.revenue) AS rev, SUM(sd.orders_units) AS orders
    FROM sales_daily sd
    JOIN products p ON p.sku = sd.sku
    WHERE sd.orders_units > 0
      AND sd.sku NOT IN (SELECT sku FROM accruals WHERE sku IS NOT NULL)
    GROUP BY p.sku
    ORDER BY rev DESC
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r['offer_id']:<18} {r['rev']:>10,.0f} ₽, заказов {r['orders']}   {(r['name'] or '')[:50]}")

con.close()
print("\n" + "=" * 100)
