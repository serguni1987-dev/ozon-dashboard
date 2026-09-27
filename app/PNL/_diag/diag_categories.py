"""
diag_categories.py — смотрим все accrued_category за август и суммы.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ACCRUED_CATEGORY ЗА АВГУСТ")
print("=" * 80)

for r in con.execute("""
    SELECT accrued_category,
           COUNT(*) AS n,
           SUM(total_amount) AS total
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY accrued_category
    ORDER BY ABS(SUM(total_amount)) DESC
"""):
    print(f"  {str(r['accrued_category']):<25} {r['n']:>5} записей  {r['total']:>12,.2f} ₽")

# Все записи, у которых нет services
print("\n" + "=" * 80)
print("ЗАПИСИ БЕЗ SERVICES (потенциально потерянные)")
print("=" * 80)

rows = con.execute("""
    SELECT a.accrual_id, a.date, a.accrued_category, a.delivery_schema,
           a.total_amount,
           (SELECT COUNT(*) FROM accruals_services s
            WHERE s.accrual_id = a.accrual_id) AS n_services
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND a.total_amount < -5
    ORDER BY a.total_amount
""").fetchall()

total_no_services = 0
total_with_services = 0
total_mismatch = 0

for r in rows:
    if r['n_services'] == 0:
        total_no_services += r['total_amount']
    else:
        # Сумма сервисов
        s = con.execute("""
            SELECT SUM(amount) FROM accruals_services WHERE accrual_id = ?
        """, (r['accrual_id'],)).fetchone()[0] or 0
        # Сравниваем с total
        if abs(s - r['total_amount']) > 1:
            total_mismatch += (r['total_amount'] - s)

print(f"\n  Записей без services:  {sum(1 for r in rows if r['n_services']==0)}")
print(f"  Сумма (без services):  {total_no_services:,.2f} ₽")
print(f"\n  Записей с services, но total != сумма services:  {sum(1 for r in rows if r['n_services']>0)}")
print(f"  Расхождение:  {total_mismatch:,.2f} ₽")

# Показываем 20 самых крупных расхождений
print(f"\n  ТОП-20 РАСХОЖДЕНИЙ:")
print(f"  {'Accrual ID':<15} {'Date':<12} {'Category':<15} {'Total':>10} {'Services':>10} {'Δ':>10}")
print("  " + "-" * 75)

mismatches = []
for r in rows:
    if r['n_services'] == 0:
        continue
    s = con.execute("SELECT SUM(amount) FROM accruals_services WHERE accrual_id = ?", (r['accrual_id'],)).fetchone()[0] or 0
    delta = r['total_amount'] - s
    if abs(delta) > 1:
        mismatches.append((r, s, delta))

mismatches.sort(key=lambda x: -abs(x[2]))
for r, s, delta in mismatches[:20]:
    print(f"  {r['accrual_id']:<15} {r['date']:<12} {str(r['accrued_category']):<15} "
          f"{r['total_amount']:>10,.2f} {s:>10,.2f} {delta:>10,.2f}")

# Ищем уникальные ID с расхождением — возможно, это AGENT или FBO
print(f"\n  УНИКАЛЬНЫЕ accrual_id из расхождений (первые 10):")
seen = set()
for r, s, delta in mismatches:
    if r['accrual_id'] not in seen:
        seen.add(r['accrual_id'])
        # Смотрим raw через API — нет, у нас нет raw. Смотрим по category
        print(f"    {r['accrual_id']}  cat={r['accrued_category']}  schema={r['delivery_schema']}  "
              f"total={r['total_amount']:.2f}  services={s:.2f}")
        if len(seen) >= 10:
            break

con.close()
print("\n" + "=" * 80)
