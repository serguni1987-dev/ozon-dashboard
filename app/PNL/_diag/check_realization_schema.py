import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Колонки monthly_realization_rows ===")
for col in c.execute("PRAGMA table_info(monthly_realization_rows)"):
    print(f"  {col['name']}  {col['type']}")

print()
print("=== Пример строки за апрель ===")
r = c.execute("""SELECT * FROM monthly_realization_rows
                 WHERE month='2026-04' LIMIT 1""").fetchone()
if r:
    for k in r.keys():
        v = r[k]
        if isinstance(v, str) and len(v) > 80:
            v = v[:80] + "..."
        print(f"  {k} = {v!r}")

print()
print("=== Суммы quantity по месяцам (если колонка есть) ===")
cols = [col["name"] for col in c.execute("PRAGMA table_info(monthly_realization_rows)")]
qty_candidates = [x for x in cols if x.lower() in ("quantity", "qty", "delivered_qty", "delivered")]
if qty_candidates:
    for qc in qty_candidates:
        print(f"  Колонка {qc!r}:")
        for row in c.execute(f"""
            SELECT month, COUNT(*) AS n, SUM({qc}) AS total
            FROM monthly_realization_rows
            GROUP BY month ORDER BY month
        """):
            print(f"    {row['month']}  n={row['n']:>4}  sum={row['total'] or 0}")
else:
    print("  Колонки с quantity НЕ найдено. Доступные:", cols)

c.close()
