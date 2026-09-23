"""
compare_sku_count.py — сравнение количества SKU из разных источников.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("КОЛИЧЕСТВО SKU ПО ИСТОЧНИКАМ (АВГУСТ 2026)")
print("=" * 80)

# 1. SKU в accruals за август
print("\n[1] accruals (начисления /v1/finance/accrual/by-day):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           COUNT(*) AS n_records,
           COUNT(DISTINCT CASE WHEN sku IS NULL THEN accrual_id END) AS n_bez_sku
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
""").fetchone()
print(f"    Уникальных SKU:    {r['n_sku']}")
print(f"    Всего записей:     {r['n_records']}")
print(f"    Без SKU:           {r['n_bez_sku']}")

# 2. SKU в sales_daily за август (с продажами)
print("\n[2] sales_daily (аналитика /v1/analytics/data):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_all,
           COUNT(DISTINCT CASE WHEN orders_units > 0 THEN sku END) AS n_with_orders,
           SUM(orders_units) AS orders,
           SUM(delivered) AS delivered
    FROM sales_daily
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
""").fetchone()
print(f"    Уникальных SKU всего:       {r['n_all']}")
print(f"    Из них с заказами:          {r['n_with_orders']}")
print(f"    Заказов:                    {r['orders']}")
print(f"    Доставлено:                 {r['delivered']}")

# 3. SKU в monthly_realization_rows (отчёт о реализации /v2/finance/realization)
print("\n[3] monthly_realization_rows (/v2/finance/realization):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           COUNT(*) AS n_rows,
           SUM(quantity) AS qty
    FROM monthly_realization_rows
    WHERE month = '2026-08'
""").fetchone()
print(f"    Уникальных SKU:    {r['n_sku']}")
print(f"    Всего строк:       {r['n_rows']}")
print(f"    Единиц товара:     {r['qty']}")

# 4. Пересечение SKU
print("\n[4] Пересечения:")
r = con.execute("""
    SELECT COUNT(DISTINCT a.sku)
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND a.sku IN (
          SELECT DISTINCT sku FROM sales_daily
          WHERE date >= '2026-08-01' AND date < '2026-09-01'
            AND orders_units > 0
      )
""").fetchone()
print(f"    accruals ∩ sales_daily (с заказами):  {r[0]}")

r = con.execute("""
    SELECT COUNT(DISTINCT a.sku)
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND a.sku IN (
          SELECT DISTINCT sku FROM monthly_realization_rows
          WHERE month = '2026-08'
      )
""").fetchone()
print(f"    accruals ∩ realization:               {r[0]}")

# 5. SKU, которые есть в realization, но нет в accruals
print("\n[5] SKU в realization, но НЕТ в accruals за август:")
rows = con.execute("""
    SELECT DISTINCT r.sku, r.offer_id, r.item_name
    FROM monthly_realization_rows r
    WHERE r.month = '2026-08'
      AND r.sku NOT IN (
          SELECT DISTINCT sku FROM accruals
          WHERE date >= '2026-08-01' AND date < '2026-09-01'
            AND sku IS NOT NULL
      )
""").fetchall()
print(f"    Найдено: {len(rows)}")
for r in rows[:20]:
    name = (r["item_name"] or "")[:50]
    print(f"      {r['sku']:<15} {r['offer_id']:<20} {name}")

# 6. SKU в accruals, которых нет в realization
print("\n[6] SKU в accruals, но НЕТ в realization:")
rows = con.execute("""
    SELECT DISTINCT a.sku
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND a.sku IS NOT NULL
      AND a.sku NOT IN (
          SELECT DISTINCT sku FROM monthly_realization_rows
          WHERE month = '2026-08'
      )
""").fetchall()
print(f"    Найдено: {len(rows)}")
for r in rows[:20]:
    print(f"      {r['sku']}")

# 7. Сводка
print("\n" + "=" * 80)
print("СВОДКА")
print("=" * 80)
print(f"""
  Источник                                      SKU      Заказов/строк
  ──────────────────────────────────────────────────────────────────
  accruals (начисления)                        {r1:>5}      {r2:>5}
  sales_daily (аналитика, с заказами)          {r3:>5}      {r4:>5}
  realization (отчёт о реализации)             {r5:>5}      {r6:>5}
""".format(
    r1=con.execute("SELECT COUNT(DISTINCT sku) FROM accruals WHERE date >= '2026-08-01' AND date < '2026-09-01'").fetchone()[0],
    r2=con.execute("SELECT COUNT(*) FROM accruals WHERE date >= '2026-08-01' AND date < '2026-09-01'").fetchone()[0],
    r3=con.execute("SELECT COUNT(DISTINCT sku) FROM sales_daily WHERE date >= '2026-08-01' AND date < '2026-09-01' AND orders_units > 0").fetchone()[0],
    r4=con.execute("SELECT SUM(orders_units) FROM sales_daily WHERE date >= '2026-08-01' AND date < '2026-09-01'").fetchone()[0] or 0,
    r5=con.execute("SELECT COUNT(DISTINCT sku) FROM monthly_realization_rows WHERE month = '2026-08'").fetchone()[0],
    r6=con.execute("SELECT COUNT(*) FROM monthly_realization_rows WHERE month = '2026-08'").fetchone()[0],
))

con.close()
