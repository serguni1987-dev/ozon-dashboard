"""check_costs_control.py — контроль себестоимости.
1. Сколько всего SKU продавалось в 2026
2. У скольких есть cost_price
3. По месяцам — сколько продаж без себестоимости
4. Топ-10 проблемных SKU (много продаж, нет себестоимости)
"""
import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=" * 80)
print("1. ОБЩАЯ СТАТИСТИКА ПО SKU")
print("=" * 80)
r = c.execute("""
    SELECT
        COUNT(DISTINCT sd.sku) AS total_sold,
        COUNT(DISTINCT CASE WHEN p.cost_price > 0 THEN sd.sku END) AS with_cost,
        COUNT(DISTINCT CASE WHEN p.cost_price IS NULL OR p.cost_price = 0 THEN sd.sku END) AS without_cost
    FROM sales_daily sd
    LEFT JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-01-01'
""").fetchone()
print(f"  Всего SKU с продажами:   {r['total_sold']}")
print(f"  С себестоимостью:        {r['with_cost']}")
print(f"  БЕЗ себестоимости:       {r['without_cost']}  ⚠")

# ─── SKU из monthly_realization_rows ───
print()
print("=" * 80)
print("2. SKU ИЗ ОТЧЁТА РЕАЛИЗАЦИИ (monthly_realization_rows)")
print("=" * 80)
r = c.execute("""
    SELECT
        COUNT(DISTINCT mr.sku) AS total,
        COUNT(DISTINCT CASE WHEN p.cost_price > 0 THEN mr.sku END) AS with_cost,
        COUNT(DISTINCT CASE WHEN p.cost_price IS NULL OR p.cost_price = 0 THEN mr.sku END) AS without_cost
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
""").fetchone()
print(f"  Всего SKU в реализации:  {r['total']}")
print(f"  С себестоимостью:        {r['with_cost']}")
print(f"  БЕЗ себестоимости:       {r['without_cost']}  ⚠")

# ─── По месяцам ───
print()
print("=" * 80)
print("3. ПРОДАЖИ БЕЗ СЕБЕСТОИМОСТИ ПО МЕСЯЦАМ (sales_daily)")
print("=" * 80)
print(f"{'Мес':<8} | {'delivered':>10} | {'без себест':>12} | {'%':>6}")
print("-" * 50)
for m in ["2026-01","2026-02","2026-03","2026-04","2026-05",
          "2026-06","2026-07","2026-08","2026-09"]:
    r = c.execute("""
        SELECT
            SUM(sd.delivered) AS total,
            SUM(CASE WHEN p.cost_price IS NULL OR p.cost_price = 0
                     THEN sd.delivered ELSE 0 END) AS missing
        FROM sales_daily sd
        LEFT JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date <= ?
    """, (f"{m}-01", f"{m}-31")).fetchone()
    t = r['total'] or 0
    ms = r['missing'] or 0
    pct = (ms / t * 100) if t else 0
    mark = "⚠" if ms > 0 else "✓"
    print(f"{m:<8} | {t:>10} | {ms:>12} | {pct:>5.1f}% {mark}")

# ─── Топ-10 проблемных ───
print()
print("=" * 80)
print("4. ТОП SKU БЕЗ СЕБЕСТОИМОСТИ (по delivered)")
print("=" * 80)
print(f"{'SKU':>12} | {'delivered':>9} | {'offer_id':<25} | {'Название':<30}")
print("-" * 85)
for r in c.execute("""
    SELECT
        sd.sku,
        SUM(sd.delivered) AS dlv,
        p.offer_id,
        p.name
    FROM sales_daily sd
    LEFT JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-01-01'
      AND (p.cost_price IS NULL OR p.cost_price = 0)
    GROUP BY sd.sku
    ORDER BY dlv DESC
    LIMIT 10
"""):
    name = (r['name'] or '')[:30]
    off = (r['offer_id'] or '')[:25]
    print(f"{r['sku']:>12} | {r['dlv']:>9} | {off:<25} | {name}")

# ─── Сколько SKU в products с cost_date ───
print()
print("=" * 80)
print("5. АКТУАЛЬНОСТЬ cost_date В products")
print("=" * 80)
r = c.execute("""
    SELECT cost_date, COUNT(*) AS n
    FROM products
    WHERE cost_price > 0
    GROUP BY cost_date
    ORDER BY cost_date DESC
""").fetchall()
if r:
    for row in r:
        print(f"  {row['cost_date']}  SKU с себестоимостью: {row['n']}")
else:
    print("  cost_date пусто — колонка не заполнена")

c.close()