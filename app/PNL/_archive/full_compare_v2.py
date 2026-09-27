"""
full_compare_v2.py — чистое сравнение с учётом знаков.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Приложение — все значения положительные (расходы тоже)
APP = {
    "Выручка": 302967.00,
    "Выручка от реализации": 161382.96,
    "Баллы за скидки": 139902.77,
    "Программы партнёров": 1681.27,
    "Комиссия Ozon": 151050.09,
    "Логистика": 9850.00,
    "Услуги агентов": 9028.22,
    "Услуги FBO": 721.00,
    "Другие услуги": 391.50,
    "Компенсации": 0.00,
    "Прочие начисления": 4686.10,
    "Реклама и ДРР": 291.75,
    "Себестоимость": 111319.00,
    "Маржа": 15629.34,
}

date_from, date_to = "2026-08-01", "2026-09-01"

# Наши данные (абсолютные значения расходов)
a = con.execute("""
    SELECT SUM(sale_price) AS slp, SUM(sale_commission) AS comm,
           SUM(bonus) AS bonus, SUM(coinvestment) AS coinv
    FROM accruals WHERE date >= ? AND date < ?
""", (date_from, date_to)).fetchone()
sale_price = a["slp"] or 0
commission = abs(a["comm"] or 0)
bonus = a["bonus"] or 0
coinvestment = a["coinv"] or 0
app_revenue = sale_price + bonus + coinvestment

# Услуги по type_id
services = {}
for r in con.execute("""
    SELECT type_id, SUM(amount) AS total
    FROM accruals_services WHERE date >= ? AND date < ?
    GROUP BY type_id
""", (date_from, date_to)):
    services[r["type_id"]] = abs(r["total"])

# Категории (как у приложения)
logist_sales = services.get(32, 0) + services.get(98, 0)  # Logistic + DeliveryToHandover
logist_returns = services.get(59, 0)  # ReturnFlowLogistic
logist_total = logist_sales + logist_returns

# Услуги агентов — как считает приложение
# Acquiring + StarsMembership + TemporaryPlacementsAgent
agents = services.get(1, 0) + services.get(74, 0) + services.get(79, 0)

# FBO — SellerReturns + Placements
fbo = services.get(71, 0) + services.get(46, 0)

# Другие услуги — DefectFineErrors
other = services.get(93, 0)

# Прочие начисления — EarlyPayment + FlexiblePayments
misc = services.get(18, 0) + services.get(20, 0)

# Реклама — BrandCommission
advertising = services.get(3, 0)

# Себестоимость
cogs = 0.0
for row in con.execute("""
    SELECT p.cost_price, SUM(sd.delivered) AS d
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
    GROUP BY p.sku
""", (date_from, date_to)):
    cogs += (row[0] or 0) * (row[1] or 0)

# Маржа
services_total = logist_total + agents + fbo + other + misc + advertising
expenses = commission + services_total
margin = app_revenue - expenses - cogs

# Сводка
OUR = {
    "Выручка": app_revenue,
    "Выручка от реализации": sale_price,
    "Баллы за скидки": bonus,
    "Программы партнёров": coinvestment,
    "Комиссия Ozon": commission,
    "Логистика": logist_total,
    "Услуги агентов": agents,
    "Услуги FBO": fbo,
    "Другие услуги": other,
    "Компенсации": 0,
    "Прочие начисления": misc,
    "Реклама и ДРР": advertising,
    "Себестоимость": cogs,
    "Маржа": margin,
}

print("=" * 100)
print("СРАВНЕНИЕ (чистое, с учётом знаков)")
print("=" * 100)
print(f"\n{'Показатель':<28} {'Приложение':>14} {'Наше':>14} {'Δ':>12} {'%':>8} {'Статус'}")
print("-" * 90)

for name, app_val in APP.items():
    our_val = OUR.get(name, 0)
    delta = our_val - app_val
    pct = (delta / abs(app_val) * 100) if app_val else 0

    if abs(delta) < 10:
        mark = "✅ точно"
    elif abs(delta) < 300:
        mark = "✅ близко"
    elif abs(delta) < 5000:
        mark = "🟡"
    else:
        mark = "❌"

    print(f"{name:<28} {app_val:>14,.2f} {our_val:>14,.2f} {delta:>+12,.2f} {pct:>+7.1f}% {mark}")

print("\n" + "=" * 100)
print("ИТОГ")
print("=" * 100)
print(f"""
  Выручка:      наше {app_revenue:>12,.2f}   приложение {APP['Выручка']:>12,.2f}   Δ {app_revenue - APP['Выручка']:>+10,.2f}  ({((app_revenue - APP['Выручка']) / APP['Выручка'] * 100):+.1f}%)
  Расходы:      наше {expenses:>12,.2f}   приложение {sum(v for k, v in APP.items() if k not in ['Выручка', 'Выручка от реализации', 'Баллы за скидки', 'Программы партнёров', 'Себестоимость', 'Маржа']):>12,.2f}
  Себестоимость: наше {cogs:>11,.2f}   приложение {APP['Себестоимость']:>12,.2f}   Δ {cogs - APP['Себестоимость']:>+10,.2f}
  Маржа:        наше {margin:>12,.2f}   приложение {APP['Маржа']:>12,.2f}   Δ {margin - APP['Маржа']:>+10,.2f}
""")

con.close()
