"""fix_dupes.py — дедупликация accruals_services + UNIQUE INDEX."""
import sqlite3
from datetime import datetime

DB = "ozon.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=== ДО ===")
n_before = c.execute("SELECT COUNT(*) FROM accruals_services").fetchone()[0]
print(f"  Строк: {n_before}")

# ── 1. Удалить дубли, оставив MIN(id) ──
print("\n[1] Удаляю дубли (оставляю минимальный id на группу)...")
c.execute("""
    DELETE FROM accruals_services
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM accruals_services
        GROUP BY accrual_id, type_id, date, amount
    )
""")
c.commit()

n_after = c.execute("SELECT COUNT(*) FROM accruals_services").fetchone()[0]
print(f"  Удалено: {n_before - n_after}")
print(f"  Осталось: {n_after}")

# ── 2. Создать UNIQUE INDEX ──
print("\n[2] Создаю UNIQUE INDEX...")
try:
    c.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_accruals_services_unique
        ON accruals_services(accrual_id, type_id, date, amount)
    """)
    c.commit()
    print("  [OK] UNIQUE INDEX создан")
except Exception as e:
    print(f"  [FAIL] {e}")

# ── 3. Проверка ──
print("\n[3] Проверка дублей по месяцам:")
for m in ["2026-01","2026-02","2026-03","2026-04","2026-05",
          "2026-06","2026-07","2026-08","2026-09"]:
    r = c.execute("""
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN cnt > 1 THEN 1 ELSE 0 END) AS dups
        FROM (
            SELECT COUNT(*) AS cnt
            FROM accruals_services
            WHERE date >= ? AND date <= ?
            GROUP BY accrual_id, type_id, date, amount
        )
    """, (f"{m}-01", f"{m}-31")).fetchone()
    flag = "⚠" if (r['dups'] or 0) > 0 else "✓"
    print(f"  {m}  строк={r['n']:>5}  дублей={r['dups'] or 0:>4}  {flag}")

c.close()
print("\n[OK] Готово")