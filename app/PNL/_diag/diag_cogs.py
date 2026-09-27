"""
diag_cogs.py — разбираемся почему себестоимость ×2.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ДИАГНОСТИКА СЕБЕСТОИМОСТИ ЗА АВГУСТ")
print("=" * 80)

# 1. Все варианты подсчёта
print(f"\n[1] Разные варианты подсчёта себестоимости:")
r = con.execute("""
    SELECT
        COUNT(*) AS rows,
        SUM(sd.orders_units) AS orders_sum,
        SUM(sd.delivered) AS delivered_sum,
        SUM(sd.purchased) AS purchased_sum,
        SUM(CASE WHEN p.cost_price > 0 THEN sd.orders_units ELSE 0 END) AS orders_with_cost,
        SUM(CASE WHEN p.cost_price > 0 THEN sd.delivered ELSE 0 END) AS delivered_with_cost,
        SUM(CASE WHEN p.cost_price > 0 THEN sd.orders_units * p.cost_price ELSE 0 END) AS cogs_orders,
        SUM(CASE WHEN p.cost_price > 0 THEN sd.delivered * p.cost_price ELSE 0 END) AS cogs_delivered,
        SUM(CASE WHEN p.cost_price > 0 THEN sd.purchased * p.cost_price ELSE 0 END) AS cogs_purchased
    FROM sales_daily sd
    JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-08-01' AND sd.date < '2026-09-01'
""").fetchone()
for k, v in dict(r).items():
    if isinstance(v, float):
        print(f"    {k:<25} {v:>14,.2f}")
    else:
        print(f"    {k:<25} {v:>14}")

# 2. Без cost_price (пропущено)
print(f"\n[2] SKU без cost_price за август:")
r = con.execute("""
    SELECT COUNT(DISTINCT p.sku) AS n, SUM(sd.orders_units) AS orders
    FROM sales_daily sd
    JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-08-01' AND sd.date < '2026-09-01'
      AND (p.cost_price IS NULL OR p.cost_price = 0)
""").fetchone()
print(f"    SKU без себестоимости: {r['n']}, заказов: {r['orders']}")

# 3. Дубли в sales_daily по одному SKU+дате
print(f"\n[3] Дубли (sku, date):")
r = con.execute("""
    SELECT COUNT(*) AS n FROM (
        SELECT sku, date, COUNT(*) AS c
        FROM sales_daily
        WHERE date >= '2026-08-01' AND date < '2026-09-01'
        GROUP BY sku, date
        HAVING c > 1
    )
""").fetchone()
print(f"    Дублей: {r['n']}")

# 4. Топ-10 SKU по вкладу в себестоимость
print(f"\n[4] Топ-10 SKU по вкладу в себестоимость:")
print(f"    {'Offer ID':<18} {'Cost':>8} {'Orders':>8} {'Delivered':>10} {'COGS(ord)':>12} {'COGS(dlv)':>12}")
print("    " + "-" * 75)
for row in con.execute("""
    SELECT p.offer_id, p.cost_price,
           SUM(sd.orders_units) AS orders,
           SUM(sd.delivered) AS delivered,
           SUM(sd.orders_units * p.cost_price) AS cogs_ord,
           SUM(sd.delivered * p.cost_price) AS cogs_dlv
    FROM sales_daily sd
    JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-08-01' AND sd.date < '2026-09-01'
      AND p.cost_price > 0
    GROUP BY p.sku
    ORDER BY cogs_ord DESC
    LIMIT 10
"""):
    print(f"    {row['offer_id']:<18} {row['cost_price']:>8,.0f} {row['orders']:>8} "
          f"{row['delivered']:>10} {row['cogs_ord']:>12,.0f} {row['cogs_dlv']:>12,.0f}")

# 5. Сверка с приложением
print(f"\n[5] Сверка с приложением:")
targets = [111319]
print(f"    Приложение:                    {111319:>14,.0f}")
print(f"    COGS orders × cost:            {r['cogs_orders']:>14,.0f}") if 'cogs_orders' in r else None
print(f"    COGS delivered × cost:         {r['cogs_delivered']:>14,.0f}")
print(f"    COGS purchased × cost:         {r['cogs_purchased']:>14,.0f}")

con.close()
print()
print("=" * 80)
