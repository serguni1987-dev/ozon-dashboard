"""
diag_pnl.py — проверка готовности к этапу P&L.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(APP_DIR, "ozon.db")

print("=" * 80)
print("ПРОВЕРКА ПРОЕКТА ДЛЯ ЭТАПА P&L")
print("=" * 80)

# 1. Файлы
print("\n[1] Ключевые файлы:")
files = [
    "sync_monthly.py",       # отчёт о реализации /v2/finance/realization
    "sync_finance.py",       # accruals /v1/finance/accrual/by-day
    "calc_monthly_summary.py",  # наш P&L
    "sync_realization.py",   # ← проверим наличие
    "sheets_sync.py",        # Google Sheets
]
for f in files:
    path = os.path.join(APP_DIR, f)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  ✅ {f:<30} ({size} байт)")
    else:
        print(f"  —  {f:<30} НЕТ")

# 2. Таблицы в БД
print("\n[2] Таблицы в БД:")
con = sqlite3.connect(DB)
for r in con.execute("""
    SELECT name FROM sqlite_master WHERE type='table'
    ORDER BY name
"""):
    n = con.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0]
    mark = "  ✅" if n > 0 else "  —"
    print(f"  {mark} {r[0]:<35} {n:>8} строк")

# 3. monthly_reports
print("\n[3] monthly_reports:")
for r in con.execute("SELECT * FROM monthly_reports"):
    keys = [d[0] for d in r.cursor.description] if hasattr(r, 'cursor') else []
    print(f"  Месяц: {r[0]}")
    # Показываем поля
    cols = [d[1] for d in con.execute("PRAGMA table_info(monthly_reports)")]
    for i, col in enumerate(cols):
        val = r[i]
        if isinstance(val, float) and val:
            print(f"    {col:<25} {val:>14,.2f}")
        elif val:
            print(f"    {col:<25} {val}")

# 4. monthly_realization_rows
print("\n[4] monthly_realization_rows:")
r = con.execute("""
    SELECT month, COUNT(*), SUM(seller_price), SUM(sale_price),
           SUM(bonus), SUM(gross_commission), SUM(effective_fee)
    FROM monthly_realization_rows GROUP BY month
""").fetchone()
if r:
    print(f"  Месяц: {r[0]}, строк: {r[1]}")
    print(f"    seller_price:     {r[2] or 0:>14,.2f}")
    print(f"    sale_price:       {r[3] or 0:>14,.2f}")
    print(f"    bonus:            {r[4] or 0:>14,.2f}")
    print(f"    gross_commission: {r[5] or 0:>14,.2f}")
    print(f"    effective_fee:    {r[6] or 0:>14,.2f}")
else:
    print("  Нет данных")

con.close()
print("\n" + "=" * 80)
