"""check_margin_sources: проверка источников данных для юнит-экономики."""
import sqlite3, os, csv

DB = "ozon.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("1. СТРУКТУРА accruals_services")
print("=" * 80)
for col in con.execute("PRAGMA table_info(accruals_services)"):
    print(f"  {col['name']:20} {col['type']}")

print()
print("=" * 80)
print("2. type_id=69 — что это?")
print("=" * 80)
r = con.execute("""
    SELECT type_id, type_name, COUNT(*) AS n, SUM(amount) AS total
    FROM accruals_services WHERE type_id = 69
    GROUP BY type_id, type_name
""").fetchall()
if r:
    for x in r:
        print(f"  id={x['type_id']} name={x['type_name']!r} n={x['n']} sum={x['total']:,.2f}")
else:
    print("  type_id=69 НЕ найден")

print()
print("  Для сравнения — type_id=32 (Logistic) есть?")
r = con.execute("""
    SELECT type_id, type_name, COUNT(*) AS n, SUM(amount) AS total
    FROM accruals_services WHERE type_id = 32
    GROUP BY type_id, type_name
""").fetchone()
if r:
    print(f"    id={r['type_id']} name={r['type_name']!r} n={r['n']} sum={r['total']:,.2f}")

print()
print("=" * 80)
print("3. Сколько услуг привязано к SKU, а сколько нет")
print("=" * 80)
r = con.execute("""
    SELECT
        SUM(CASE WHEN sku IS NOT NULL THEN 1 ELSE 0 END) AS with_sku,
        SUM(CASE WHEN sku IS NULL THEN 1 ELSE 0 END) AS without_sku,
        COUNT(*) AS total
    FROM accruals_services
""").fetchone()
print(f"  С SKU:     {r['with_sku']:,}")
print(f"  Без SKU:   {r['without_sku']:,}")
print(f"  Всего:     {r['total']:,}")

print()
print("  Разбивка по категориям (по type_id из CATEGORY_MAP):")
CATS = {
    "Логистика": (32, 59, 98, 16, 17, 38, 39),
    "Услуги агентов": (1, 74, 79, 29, 45),
    "Услуги FBO": (46, 71, 76, 12),
    "Маркетинг": (41, 54, 3, 47, 96, 22, 52, 48),
    "Комиссия": (69,),
}
for cat, ids in CATS.items():
    ph = ",".join("?" * len(ids))
    r = con.execute(f"""
        SELECT
            SUM(CASE WHEN sku IS NOT NULL THEN 1 ELSE 0 END) AS with_sku,
            SUM(CASE WHEN sku IS NULL THEN 1 ELSE 0 END) AS without_sku,
            SUM(CASE WHEN sku IS NOT NULL THEN ABS(amount) ELSE 0 END) AS sum_with_sku,
            SUM(CASE WHEN sku IS NULL THEN ABS(amount) ELSE 0 END) AS sum_without_sku
        FROM accruals_services WHERE type_id IN ({ph})
    """, ids).fetchone()
    print(f"  {cat:20}  с SKU: {r['with_sku']:>5} ({r['sum_with_sku'] or 0:>14,.2f})   "
          f"без SKU: {r['without_sku']:>5} ({r['sum_without_sku'] or 0:>14,.2f})")

print()
print("=" * 80)
print("4. Комиссия: gross_commission из realization vs accruals_services")
print("=" * 80)
# Из realization
r = con.execute("""
    SELECT month, SUM(gross_commission) AS sum_comm FROM monthly_realization_rows
    GROUP BY month ORDER BY month
""").fetchall()
print("  gross_commission из monthly_realization_rows:")
for x in r:
    print(f"    {x['month']}  {x['sum_comm'] or 0:>14,.2f}")

# Из accruals_services — если есть type_id=69
r = con.execute("""
    SELECT substr(date, 1, 7) AS m, SUM(ABS(amount)) AS total
    FROM accruals_services WHERE type_id = 69
    GROUP BY m ORDER BY m
""").fetchall()
if r:
    print("  type_id=69 из accruals_services:")
    for x in r:
        print(f"    {x['m']}  {x['total']:>14,.2f}")
else:
    print("  type_id=69 нет в accruals_services — комиссия доступна только из realization")

print()
print("=" * 80)
print("5. Все type_id в accruals_services (свежий срез)")
print("=" * 80)
r = con.execute("""
    SELECT type_id, type_name, COUNT(*) AS n,
           SUM(CASE WHEN sku IS NOT NULL THEN 1 ELSE 0 END) AS with_sku,
           SUM(ABS(amount)) AS total
    FROM accruals_services
    GROUP BY type_id, type_name ORDER BY total DESC
""").fetchall()
for x in r:
    has_sku = "✓SKU" if x['with_sku'] > 0 else "  — "
    print(f"  id={x['type_id']:>4} {has_sku}  n={x['n']:>5}  sum={x['total']:>14,.2f}  {x['type_name']!r}")

print()
print("=" * 80)
print("6. Себестоимость: история в БД vs CSV")
print("=" * 80)
r = con.execute("SELECT COUNT(*) AS n, COUNT(DISTINCT sku) AS skus FROM product_cost_history").fetchone()
print(f"  product_cost_history:  {r['n']} записей, {r['skus']} SKU")

csv_path = os.path.join("Себестоимость", "costs_all.csv")
if os.path.exists(csv_path):
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))
    print(f"  costs_all.csv:         {len(rows)-1} строк, колонки: {rows[0]}")
else:
    print(f"  costs_all.csv: НЕ найден по пути {csv_path}")

con.close()
