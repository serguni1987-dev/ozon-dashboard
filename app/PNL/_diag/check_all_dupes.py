import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Дубли по месяцам ===")
for m in ["2026-01","2026-02","2026-03","2026-04","2026-05",
          "2026-06","2026-07","2026-08","2026-09"]:
    r = c.execute("""
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN cnt > 1 THEN 1 ELSE 0 END) AS dup_groups,
               SUM(CASE WHEN cnt > 1 THEN cnt - 1 ELSE 0 END) AS extra_rows
        FROM (
            SELECT COUNT(*) AS cnt
            FROM accruals_services
            WHERE date >= ? AND date <= ?
            GROUP BY accrual_id, type_id, date, amount
        )
    """, (f"{m}-01", f"{m}-31")).fetchone()
    n = r['n'] or 0
    dg = r['dup_groups'] or 0
    ex = r['extra_rows'] or 0
    flag = "⚠" if ex > 0 else "✓"
    print(f"  {m}  групп={n:>5}  с дублями={dg:>4}  лишних строк={ex:>5}  {flag}")

print()
print("=== Итог по всей accruals_services ===")
r = c.execute("SELECT COUNT(*) FROM accruals_services").fetchone()[0]
print(f"  Всего строк: {r}")
r = c.execute("""
    SELECT COUNT(*) FROM (
        SELECT 1 FROM accruals_services
        GROUP BY accrual_id, type_id, date, amount
    )
""").fetchone()[0]
print(f"  Уникальных: {r}")
print(f"  Дублей: {r - r}")

print()
print("=== Есть ли UNIQUE constraint на accruals_services? ===")
for r in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='accruals_services'"):
    print(r['sql'])