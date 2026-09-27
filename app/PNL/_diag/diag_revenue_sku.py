"""
diag_revenue_sku.py - разбор расхождения выручки -3%.
Сравниваем SKU по источникам.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

date_from = "2026-08-01"
date_to = "2026-09-01"

print("=" * 90)
print("РАЗБОР ВЫРУЧКИ -3%: СРАВНЕНИЕ SKU ПО ИСТОЧНИКАМ (АВГУСТ 2026)")
print("=" * 90)

# 1. sales_daily — все что продавалось
print("\n[1] sales_daily (аналитика по товарам):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           SUM(orders_units) AS orders,
           SUM(delivered) AS delivered,
           SUM(purchased) AS purchased,
           SUM(cancelled) AS cancelled,
           SUM(returned_by_return_date) AS returned,
           SUM(revenue) AS revenue
    FROM sales_daily
    WHERE date >= ? AND date < ?
""", (date_from, date_to)).fetchone()
print(f"    Уникальных SKU:     {r['n_sku']}")
print(f"    Заказано единиц:    {r['orders']}")
print(f"    Доставлено:         {r['delivered']}")
print(f"    Выкуплено:          {r['purchased']}")
print(f"    Отменено:           {r['cancelled']}")
print(f"    Возвращено:         {r['returned']}")
print(f"    Выручка:            {r['revenue'] or 0:>14,.2f}")

# 2. sales_daily — только с заказами (актуальный P&L)
print("\n[2] sales_daily — только доставленные:")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           SUM(delivered) AS delivered,
           SUM(revenue) AS revenue
    FROM sales_daily
    WHERE date >= ? AND date < ? AND delivered > 0
""", (date_from, date_to)).fetchone()
print(f"    Уникальных SKU:     {r['n_sku']}")
print(f"    Доставлено единиц:  {r['delivered']}")

# 3. accruals — начисления
print("\n[3] accruals (начисления /v1/finance/accrual/by-day):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           COUNT(*) AS records,
           SUM(sale_price) AS slp,
           SUM(sale_commission) AS comm,
           SUM(bonus) AS bonus
    FROM accruals
    WHERE date >= ? AND date < ?
      AND sku IS NOT NULL
""", (date_from, date_to)).fetchone()
print(f"    Уникальных SKU:     {r['n_sku']}")
print(f"    Записей:            {r['records']}")
print(f"    sale_price:         {r['slp'] or 0:>14,.2f}")

# 4. monthly_realization_rows — отчёт о реализации
print("\n[4] monthly_realization_rows (/v2/finance/realization):")
r = con.execute("""
    SELECT COUNT(DISTINCT sku) AS n_sku,
           COUNT(*) AS rows,
           SUM(quantity) AS qty,
           SUM(sale_price) AS slp,
           SUM(bonus) AS bonus
    FROM monthly_realization_rows
    WHERE month = '2026-08'
""").fetchone()
print(f"    Уникальных SKU:     {r['n_sku']}")
print(f"    Строк:              {r['rows']}")
print(f"    Единиц товара:      {r['qty']}")
print(f"    sale_price:         {r['slp'] or 0:>14,.2f}")
print(f"    bonus:              {r['bonus'] or 0:>14,.2f}")

# 5. SKU в accruals, но НЕ в realization
print("\n[5] SKU в accruals, но НЕ в realization (влияют на -3%):")
rows = con.execute("""
    SELECT DISTINCT a.sku,
           SUM(a.sale_price) AS slp,
           SUM(a.bonus) AS bonus,
           COUNT(*) AS n
    FROM accruals a
    WHERE a.date >= ? AND a.date < ?
      AND a.sku IS NOT NULL
      AND a.sku NOT IN (
          SELECT DISTINCT sku FROM monthly_realization_rows
          WHERE month = '2026-08'
      )
    GROUP BY a.sku
    ORDER BY SUM(a.sale_price) DESC
""", (date_from, date_to)).fetchall()
print(f"    Найдено: {len(rows)}")
total_lost = 0
for r in rows:
    print(f"      {r['sku']:<15} sale_price={r['slp'] or 0:>10,.2f}  bonus={r['bonus'] or 0:>10,.2f}  записей={r['n']}")
    total_lost += (r['slp'] or 0)
print(f"    Сумма потерянная:   {total_lost:>14,.2f}")

# 6. SKU в realization, но НЕ в accruals
print("\n[6] SKU в realization, но НЕ в accruals:")
rows = con.execute("""
    SELECT DISTINCT r.sku, r.offer_id,
           r.sale_price, r.bonus, r.quantity
    FROM monthly_realization_rows r
    WHERE r.month = '2026-08'
      AND r.sku NOT IN (
          SELECT DISTINCT sku FROM accruals
          WHERE date >= ? AND date < ?
            AND sku IS NOT NULL
      )
""", (date_from, date_to)).fetchall()
print(f"    Найдено: {len(rows)}")
for r in rows:
    print(f"      {r['sku']:<15} {r['offer_id']:<20} sale={r['sale_price'] or 0:>10,.2f}  bonus={r['bonus'] or 0:>10,.2f}")

# 7. Сверка выручки
print("\n" + "=" * 90)
print("СВЕРКА ВЫРУЧКИ")
print("=" * 90)
print(f"\n  Приложение (файл):          {302967.00:>14,.2f}")
print(f"  Наше (accruals):            {293771.00:>14,.2f}")
print(f"  Δ:                          {293771.00 - 302967.00:>+14,.2f}  ({(293771.00 - 302967.00) / 302967.00 * 100:+.1f}%)")

# Гипотеза 1: пропущенные дни
print(f"\n  ГИПОТЕЗА 1 — пропущенные дни августа:")
loaded_days = con.execute("""
    SELECT COUNT(DISTINCT date) FROM accruals
    WHERE date >= ? AND date < ?
""", (date_from, date_to)).fetchone()[0]
print(f"    Дней с начислениями:     {loaded_days} из 31")
print(f"    Если 5 дней × ~6 000 ₽ = ~30 000 ₽ — могло дать разницу")

# Гипотеза 2: расхождение по дням
print(f"\n  ГИПОТЕЗА 2 — по дням (accruals vs sales_daily):")
rows = con.execute("""
    SELECT a.date,
           SUM(a.sale_price) AS a_slp,
           (SELECT SUM(sd.revenue) FROM sales_daily sd
            WHERE sd.date = a.date) AS sd_rev
    FROM accruals a
    WHERE a.date >= ? AND a.date < ?
    GROUP BY a.date
    ORDER BY a.date
""", (date_from, date_to)).fetchall()
print(f"    {'Дата':<12} {'accruals.sale':>14} {'sales_daily.rev':>16} {'Δ':>12}")
print("    " + "-" * 58)
for r in rows[:31]:
    delta = (r['sd_rev'] or 0) - (r['a_slp'] or 0)
    print(f"    {r['date']:<12} {r['a_slp'] or 0:>14,.2f} {r['sd_rev'] or 0:>16,.2f} {delta:>+12,.2f}")

con.close()
print("\n" + "=" * 90)
