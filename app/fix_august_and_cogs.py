"""
fix_august_and_cogs.py — 1) дозагрузка пропущенных дней, 2) себестоимость по accruals.
"""
import os
import sqlite3
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
PY = sys.executable

# === 1. Дозагружаем пропущенные дни ===
missing_days = ["2026-08-11", "2026-08-18", "2026-08-21", "2026-08-22", "2026-08-30"]

print("=" * 80)
print("ДОЗАГРУЗКА ПРОПУЩЕННЫХ ДНЕЙ АВГУСТА")
print("=" * 80)

for day in missing_days:
    print(f"\n>>> Загружаем {day}...")
    r = subprocess.run(
        [PY, "sync_finance.py", f"--from={day}", f"--to={day}"],
        cwd=APP_DIR, capture_output=True, text=True,
    )
    # Ищем строку "Записей accruals:"
    for line in r.stdout.split("\n"):
        if "Записей accruals" in line or "Записей services" in line:
            print(f"    {line.strip()}")

print("\n[OK] Дозагрузка завершена")

# === 2. Себестоимость по accruals (реализованное) ===
print("\n" + "=" * 80)
print("СЕБЕСТОИМОСТЬ ПО ACCRUALS (реализованное)")
print("=" * 80)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Себестоимость SKU, по которым были начисления за август
r = con.execute("""
    SELECT COUNT(DISTINCT a.sku) AS n_sku,
           SUM(p.cost_price) AS total_cost
    FROM accruals a
    JOIN products p ON p.sku = a.sku
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND p.cost_price > 0
""").fetchone()

# Но нам нужна себестоимость ПО КАЖДОЙ ПРОДАЖЕ, а не по уникальному SKU
# Поэтому берём distinct accrual_id
r2 = con.execute("""
    SELECT COUNT(*) AS n_accruals,
           COUNT(DISTINCT a.accrual_id) AS n_distinct,
           SUM(p.cost_price) AS cogs_from_accruals
    FROM accruals a
    JOIN products p ON p.sku = a.sku
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND p.cost_price > 0
      AND a.accrued_category = 'POSTING'
""").fetchone()

print(f"\n  Уникальных SKU в accruals за август: {r['n_sku']}")
print(f"  Записей accruals (POSTING): {r2['n_accruals']}")
print(f"  Уникальных accrual_id: {r2['n_distinct']}")
print(f"  Себестоимость по accruals: {r2['cogs_from_accruals'] or 0:,.2f} ₽")

# === 3. Сравнение всех методов ===
print(f"\n  СРАВНЕНИЕ:")
print(f"    Приложение:                    111 319 ₽")
print(f"    orders × cost:                 223 483 ₽")
print(f"    delivered × cost:              122 951 ₽")
print(f"    purchased × cost:              146 854 ₽")
print(f"    accruals × cost:               {r2['cogs_from_accruals'] or 0:>10,.0f} ₽")

con.close()
print("\n" + "=" * 80)
