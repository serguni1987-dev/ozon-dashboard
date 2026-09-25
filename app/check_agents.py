import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Агенты за 25.05 — 04.07 ===")
for r in c.execute("""
    SELECT date, type_id, type_name, amount, accrual_id
    FROM accruals_services
    WHERE type_id IN (1, 18, 20, 22)
      AND date >= '2026-05-25' AND date <= '2026-07-04'
    ORDER BY date
"""):
    print(f"  {r['date']}  id={r['type_id']:>3}  {r['amount']:>10.2f}  {r['type_name']}")

print()
print("=== Агенты строго за июнь (01.06 — 30.06) ===")
total = 0
for r in c.execute("""
    SELECT date, type_id, type_name, amount
    FROM accruals_services
    WHERE type_id IN (1, 18, 20, 22)
      AND date >= '2026-06-01' AND date <= '2026-06-30'
    ORDER BY date
"""):
    print(f"  {r['date']}  id={r['type_id']:>3}  {r['amount']:>10.2f}  {r['type_name']}")
    total += r['amount']
print(f"  ИТОГО за июнь: {total:.2f}")

print()
print("=== Что попадает в фильтр P&L (date >= 01.06 AND date < 01.07) ===")
total2 = 0
for r in c.execute("""
    SELECT date, type_id, amount
    FROM accruals_services
    WHERE type_id IN (1, 18, 20, 22)
      AND date >= '2026-06-01' AND date < '2026-07-01'
"""):
    total2 += r['amount']
print(f"  ИТОГО в P&L-фильтре: {abs(total2):.2f}")