"""
diag_data_coverage.py - проверяем, за какие месяцы есть данные.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ПОКРЫТИЕ ДАННЫХ ПО МЕСЯЦАМ")
print("=" * 80)

# 1. sales_daily — за какие месяцы есть строки
print("\n[1] sales_daily по месяцам:")
for r in con.execute("""
    SELECT substr(date, 1, 7) AS m,
           COUNT(*) AS rows,
           SUM(delivered) AS delivered,
           SUM(revenue) AS revenue
    FROM sales_daily
    GROUP BY m
    ORDER BY m
"""):
    print(f"  {r['m']}  строк: {r['rows']:>6}  delivered: {r['delivered'] or 0:>5}  revenue: {r['revenue'] or 0:>12,.2f}")

# 2. accruals — за какие месяцы
print("\n[2] accruals по месяцам:")
for r in con.execute("""
    SELECT substr(date, 1, 7) AS m,
           COUNT(*) AS rows,
           SUM(sale_price) AS slp
    FROM accruals
    GROUP BY m
    ORDER BY m
"""):
    print(f"  {r['m']}  строк: {r['rows']:>6}  sale_price: {r['slp'] or 0:>12,.2f}")

# 3. monthly_realization_rows по месяцам
print("\n[3] monthly_realization_rows:")
for r in con.execute("""
    SELECT month, COUNT(*) AS rows, SUM(sale_price) AS slp
    FROM monthly_realization_rows
    GROUP BY month
    ORDER BY month
"""):
    print(f"  {r['month']}  строк: {r['rows']:>6}  sale_price: {r['slp'] or 0:>12,.2f}")

# 4. Какие SKU в realization за январь-июль
print("\n[4] SKU в realization за январь-июль (первые 10):")
for r in con.execute("""
    SELECT DISTINCT sku FROM monthly_realization_rows
    WHERE month < '2026-08'
    ORDER BY sku LIMIT 10
"""):
    sku = r["sku"]
    # Проверяем есть ли этот SKU в sales_daily
    has_sales = con.execute(
        "SELECT COUNT(*) FROM sales_daily WHERE sku = ?", (sku,)
    ).fetchone()[0]
    has_cost = con.execute(
        "SELECT cost_price FROM products WHERE sku = ?", (sku,)
    ).fetchone()
    cost = has_cost["cost_price"] if has_cost else None
    print(f"    SKU {sku}: sales_daily={has_sales}, cost_price={cost}")

con.close()
