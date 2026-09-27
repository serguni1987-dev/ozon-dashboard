"""
calc_fact_exact.py — точный расчёт по SKU из отчёта о реализации.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
TAX_RATE = 0.15

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ТОЧНЫЙ РАСЧЁТ ПО SKU ИЗ ОТЧЁТА О РЕАЛИЗАЦИИ")
print("=" * 80)

# SKU из отчёта о реализации за август
real_skus = [r[0] for r in con.execute("""
    SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = '2026-08'
""")]
print(f"\n[1] SKU в отчёте о реализации: {len(real_skus)}")

# Суммы по этим SKU из accruals
placeholders = ",".join("?" * len(real_skus))
r = con.execute(f"""
    SELECT COUNT(*) AS n,
           SUM(sale_price) AS slp,
           SUM(sale_commission) AS comm,
           SUM(bonus) AS bonus,
           SUM(coinvestment) AS coinv,
           SUM(seller_price) AS sp
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND sku IN ({placeholders})
""", real_skus).fetchone()

print(f"\n[2] Суммы по этим SKU в accruals:")
print(f"    Записей:          {r['n']}")
print(f"    seller_price:     {r['sp'] or 0:>14,.2f}")
print(f"    sale_price:       {r['slp'] or 0:>14,.2f}")
print(f"    sale_commission:  {r['comm'] or 0:>14,.2f}")
print(f"    bonus:            {r['bonus'] or 0:>14,.2f}")
print(f"    coinvestment:     {r['coinv'] or 0:>14,.2f}")

# Для сравнения — все accruals за август
r2 = con.execute("""
    SELECT SUM(sale_price) AS slp, SUM(sale_commission) AS comm,
           SUM(bonus) AS bonus, SUM(coinvestment) AS coinv
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
""").fetchone()

print(f"\n[3] ВСЕ accruals за август:")
print(f"    sale_price:       {r2['slp'] or 0:>14,.2f}")
print(f"    sale_commission:  {r2['comm'] or 0:>14,.2f}")
print(f"    bonus:            {r2['bonus'] or 0:>14,.2f}")
print(f"    coinvestment:     {r2['coinv'] or 0:>14,.2f}")

# Сравнение с приложением
print(f"\n[4] СРАВНЕНИЕ С ПРИЛОЖЕНИЕМ:")
app_slp = 161382.96  # выручка от реализации из приложения
app_bonus = 139902.77
app_comm = -151050.09
app_coinv = 1681.27

print(f"    {'Метрика':<20} {'Все accruals':>15} {'Только realization':>20} {'Приложение':>15}")
print("    " + "-" * 72)
print(f"    {'sale_price':<20} {r2['slp'] or 0:>15,.2f} {r['slp'] or 0:>20,.2f} {app_slp:>15,.2f}")
print(f"    {'sale_commission':<20} {r2['comm'] or 0:>15,.2f} {r['comm'] or 0:>20,.2f} {app_comm:>15,.2f}")
print(f"    {'bonus':<20} {r2['bonus'] or 0:>15,.2f} {r['bonus'] or 0:>20,.2f} {app_bonus:>15,.2f}")
print(f"    {'coinvestment':<20} {r2['coinv'] or 0:>15,.2f} {r['coinv'] or 0:>20,.2f} {app_coinv:>15,.2f}")

con.close()
