"""
diag_august.py — что есть за август 2026 в БД.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ЧТО ЕСТЬ ЗА АВГУСТ 2026")
print("=" * 80)

# 1. accruals
print(f"\n[1] accruals (начисления из /v1/finance/accrual/by-day):")
try:
    r = con.execute("""
        SELECT MIN(date) AS d1, MAX(date) AS d2, COUNT(*) AS n
        FROM accruals
    """).fetchone()
    print(f"    Период в БД: {r['d1']} — {r['d2']}, всего: {r['n']}")

    r2 = con.execute("""
        SELECT COUNT(*) AS n,
               SUM(sale_price) AS slp,
               SUM(sale_commission) AS comm,
               SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv
        FROM accruals
        WHERE date BETWEEN '2026-08-01' AND '2026-08-31'
    """).fetchone()
    print(f"    За август: {r2['n']} записей")
    if r2['n']:
        print(f"      sale_price:       {r2['slp'] or 0:>14,.2f}")
        print(f"      sale_commission:  {r2['comm'] or 0:>14,.2f}")
        print(f"      bonus:            {r2['bonus'] or 0:>14,.2f}")
        print(f"      coinvestment:     {r2['coinv'] or 0:>14,.2f}")
    else:
        print("    ❌ ЗА АВГУСТ НЕТ ДАННЫХ В accruals")
        print("    → нужно дозагрузить через sync_finance.py")
except Exception as e:
    print(f"    Ошибка: {e}")

# 2. accruals_services за август
print(f"\n[2] accruals_services (услуги Ozon):")
try:
    r = con.execute("""
        SELECT COUNT(*) AS n, SUM(amount) AS total
        FROM accruals_services
        WHERE date BETWEEN '2026-08-01' AND '2026-08-31'
    """).fetchone()
    print(f"    Записей: {r['n']}, сумма: {r['total'] or 0:,.2f} ₽")

    # По типам
    print(f"\n    Топ-10 услуг за август:")
    for row in con.execute("""
        SELECT type_name, SUM(amount) AS total, COUNT(*) AS n
        FROM accruals_services
        WHERE date BETWEEN '2026-08-01' AND '2026-08-31'
        GROUP BY type_name
        ORDER BY ABS(SUM(amount)) DESC
        LIMIT 10
    """):
        print(f"      {row['type_name']:<40} {row['total']:>12,.2f} ₽ ({row['n']})")
except Exception as e:
    print(f"    Ошибка: {e}")

# 3. sales_daily за август
print(f"\n[3] sales_daily:")
r = con.execute("""
    SELECT COUNT(*) AS n,
           COUNT(DISTINCT sku) AS sku_count,
           SUM(revenue) AS rev,
           SUM(orders_units) AS orders
    FROM sales_daily
    WHERE date BETWEEN '2026-08-01' AND '2026-08-31'
""").fetchone()
print(f"    Записей: {r['n']}, SKU: {r['sku_count']}")
print(f"    Выручка: {r['rev'] or 0:,.2f} ₽")
print(f"    Заказов: {r['orders'] or 0}")

# 4. monthly_reports
print(f"\n[4] monthly_reports:")
for r in con.execute("SELECT * FROM monthly_reports"):
    print(f"    Месяц: {r['month']}")
    print(f"      seller_price:       {r['seller_price_sum']:>14,.2f}")
    print(f"      sale_price:         {r['sale_price_sum']:>14,.2f}")
    print(f"      gross_commission:   {r['gross_commission_sum']:>14,.2f}")
    print(f"      bonus:              {r['bonus_sum']:>14,.2f}")
    print(f"      coinvestment:       {r['coinvestment_sum']:>14,.2f}")
    print(f"      logistics:          {r['logistics_sum']:>14,.2f}")
    print(f"      effective_fee:      {r['effective_fee_sum']:>14,.2f}")
    print(f"      net_profit:         {r['net_profit']:>14,.2f}")

# 5. Целевые цифры из файла
print(f"\n[5] ЦЕЛЕВЫЕ ЦИФРЫ (из файла приложения):")
targets = [
    ("Выручка суммарно", 302967),
    ("Выручка от реализации", 161382.96),
    ("Баллы за скидки", 139902.77),
    ("Программы партнёров", 1681.27),
    ("Расходы", 175726.91),
    ("Комиссия Ozon", 151050.09),
    ("Логистика", 9850),
    ("Услуги агентов", 9028.22),
    ("Услуги FBO", 721),
    ("Другие услуги и штрафы", 391.5),
    ("Прочие начисления", 4686.1),
    ("Себестоимость", 111319),
    ("Маржа", 15629.34),
    ("Налоги 7%", 11414.5),
    ("Чистая прибыль 7%", 4214.84),
    ("Чистая прибыль 15%", -8831),
]
for name, val in targets:
    print(f"    {name:<35} {val:>14,.2f} ₽")

con.close()
print("\n" + "=" * 80)
