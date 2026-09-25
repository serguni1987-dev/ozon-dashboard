import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Май: всего vs уникальных accrual_id по каждой услуге ===\n")
for r in c.execute("""
    SELECT type_id, type_name,
           COUNT(*) AS n,
           COUNT(DISTINCT accrual_id) AS uniq,
           SUM(ABS(amount)) AS total,
           ROUND(SUM(ABS(amount)) / COUNT(DISTINCT accrual_id), 2) AS avg_per_accrual
    FROM accruals_services
    WHERE date >= '2026-05-01' AND date <= '2026-05-31'
    GROUP BY type_id, type_name
    ORDER BY total DESC
"""):
    ratio = r['n'] / r['uniq'] if r['uniq'] else 0
    flag = "⚠ ДУБЛИ" if ratio > 1.05 else "✓"
    print(f"  id={r['type_id']:>4}  n={r['n']:>3}  uniq={r['uniq']:>3}  "
          f"sum={r['total']:>11,.2f}  ×{ratio:>4.2f}  {flag}  {r['type_name']}")

print()
print("=== Примеры дублей (5 записей с одинаковым accrual_id+type_id) ===\n")
for r in c.execute("""
    SELECT accrual_id, type_id, type_name, date, COUNT(*) AS n, amount
    FROM accruals_services
    WHERE date >= '2026-05-01' AND date <= '2026-05-31'
    GROUP BY accrual_id, type_id, date, amount
    HAVING COUNT(*) > 1
    ORDER BY n DESC, date
    LIMIT 10
"""):
    print(f"  accrual_id={r['accrual_id']}  id={r['type_id']:>3}  "
          f"date={r['date']}  amount={r['amount']:>9.2f}  count={r['n']}")

print()
print("=== Для сравнения: Август (где всё верно) ===")
for r in c.execute("""
    SELECT type_id, type_name,
           COUNT(*) AS n,
           COUNT(DISTINCT accrual_id) AS uniq,
           SUM(ABS(amount)) AS total
    FROM accruals_services
    WHERE date >= '2026-08-01' AND date <= '2026-08-31'
    GROUP BY type_id, type_name
    ORDER BY total DESC
    LIMIT 8
"""):
    ratio = r['n'] / r['uniq'] if r['uniq'] else 0
    flag = "⚠ ДУБЛИ" if ratio > 1.05 else "✓"
    print(f"  id={r['type_id']:>4}  n={r['n']:>3}  uniq={r['uniq']:>3}  "
          f"sum={r['total']:>11,.2f}  ×{ratio:>4.2f}  {flag}  {r['type_name']}")