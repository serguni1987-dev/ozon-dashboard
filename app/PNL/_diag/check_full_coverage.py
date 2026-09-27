import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=" * 70)
print("ВСЕ ТАБЛИЦЫ В БД")
print("=" * 70)
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    t = r['name']
    if t == 'sqlite_sequence':
        continue
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<35} {n:>8}")

print()
print("=" * 70)
print("ПОКРЫТИЕ ПО МЕСЯЦАМ (ключевые таблицы)")
print("=" * 70)

TABLES = [
    ("accruals", "date"),
    ("accruals_services", "date"),
    ("monthly_realization_rows", "month"),
    ("monthly_reports", "month"),
    ("sales_daily", "date"),
    ("payouts", "date"),
    ("balance_history", "date"),
    ("pending_orders", "date"),
    ("price_changes", "date"),
]

MONTHS = ["2026-01","2026-02","2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09"]

for table, col in TABLES:
    print(f"\n── {table} (по {col}) ──")
    try:
        for m in MONTHS:
            if col == "month":
                q = f"SELECT COUNT(*) FROM {table} WHERE {col} = ?"
                n = c.execute(q, (m,)).fetchone()[0]
            else:
                q = f"SELECT COUNT(*) FROM {table} WHERE {col} >= ? AND {col} <= ?"
                n = c.execute(q, (f"{m}-01", f"{m}-31")).fetchone()[0]
            mark = "✓" if n > 0 else "✗"
            print(f"  {m}  {n:>7}  {mark}")
    except Exception as e:
        print(f"  [ошибка] {e}")

print()
print("=" * 70)
print("META — когда синкали")
print("=" * 70)
try:
    for r in c.execute("SELECT * FROM ingest_log ORDER BY 1"):
        print(" ", dict(r))
except Exception as e:
    print(f"  ingest_log: {e}")