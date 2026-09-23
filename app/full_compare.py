"""
full_compare.py — построчное сравнение всех значений из файла и БД.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Данные из приложения
APP = {
    # Сводка
    "Выручка суммарно": 302967.00,
    "Выручка от реализации": 161382.96,
    "Баллы за скидки": 139902.77,
    "Программы партнёров": 1681.27,
    "Расходы": 175726.91,
    "Реклама и ДРР": 291.75,
    "Себестоимость": 111319.00,
    "Маржа": 15629.34,
    "Доп. расходы": 0.00,
    "Налоги (7%)": 11414.50,
    "Чистая прибыль (7%)": 4214.84,
    # Детализация расходов
    "Комиссия Ozon": 151050.09,
    "Логистика": 9850.00,
    "Услуги агентов": 9028.22,
    "Услуги FBO": 721.00,
    "Другие услуги и штрафы": 391.50,
    "Компенсации": 0.00,
    "Прочие начисления": 4686.10,
    # Логистика детально
    "Логистика продаж": 8705.00,
    "Логистика отмен и возвратов": 1145.00,
    # Налоги
    "Налогооблогаемая база": 163064.23,
}

# Получаем наши значения
date_from, date_to = "2026-08-01", "2026-09-01"

# Выручка/комиссия/баллы
a = con.execute("""
    SELECT SUM(seller_price) AS sp, SUM(sale_price) AS slp,
           SUM(sale_commission) AS comm, SUM(bonus) AS bonus,
           SUM(coinvestment) AS coinv
    FROM accruals WHERE date >= ? AND date < ?
""", (date_from, date_to)).fetchone()
seller_price = a["sp"] or 0
sale_price = a["slp"] or 0
commission = a["comm"] or 0
bonus = a["bonus"] or 0
coinvestment = a["coinv"] or 0

# Услуги по типам
services = {}
for r in con.execute("""
    SELECT type_id, type_name, SUM(amount) AS total
    FROM accruals_services WHERE date >= ? AND date < ?
    GROUP BY type_id, type_name
""", (date_from, date_to)):
    services[r["type_name"]] = (r["type_id"], r["total"])

# Категории
def get_total(*names):
    return sum(services.get(n, (0, 0))[1] for n in names)

logist_sales = get_total("Logistic")
logist_returns = get_total("ReturnFlowLogistic")
logist_delivery = get_total("DeliveryToHandoverPlaceByOzon")
logist_lastmile = get_total("LastMileCourier")
logist_total = logist_sales + logist_returns + logist_delivery + logist_lastmile

agents = get_total("Acquiring", "StarsMembership", "BrandCommission", "TemporaryPlacementsAgent")
fbo = get_total("SellerReturns", "Placements", "StockInsurance")
other = get_total("DefectFineErrors", "PickUpPointReturnAcceptance")
comp = get_total("Compensation", "ItemCompensation")
misc = get_total("EarlyPayment", "FlexiblePayments")
advertising = get_total("PayPerClick", "Marketing", "Promotion", "ExternalPromotion", "InternetSiteAdvertising")

app_revenue = sale_price + bonus + coinvestment

# Себестоимость (delivered)
cogs = 0.0
for row in con.execute("""
    SELECT p.cost_price, SUM(sd.delivered) AS d
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
    GROUP BY p.sku
""", (date_from, date_to)):
    cogs += (row[0] or 0) * (row[1] or 0)

# Итоги
services_total = logist_total + agents + fbo + other + comp + misc
expenses_total = abs(commission) + abs(services_total)
margin = app_revenue - expenses_total - cogs
tax_base = app_revenue - bonus
tax_15 = tax_base * 0.15
tax_7 = tax_base * 0.07
net_15 = margin - tax_15
net_7 = margin - tax_7

# Наши значения
OUR = {
    "Выручка суммарно": app_revenue,
    "Выручка от реализации": sale_price,
    "Баллы за скидки": bonus,
    "Программы партнёров": coinvestment,
    "Расходы": -expenses_total,
    "Реклама и ДРР": advertising,
    "Себестоимость": cogs,
    "Маржа": margin,
    "Доп. расходы": 0.00,
    "Налоги (15%)": tax_15,
    "Чистая прибыль (15%)": net_15,
    "Комиссия Ozon": commission,
    "Логистика": logist_total,
    "Услуги агентов": agents,
    "Услуги FBO": fbo,
    "Другие услуги и штрафы": other,
    "Компенсации": comp,
    "Прочие начисления": misc,
    "Логистика продаж": logist_sales + logist_delivery,
    "Логистика отмен и возвратов": logist_returns,
    "Налогооблогаемая база": tax_base,
}

# Вывод
print("=" * 100)
print("ПОЛНОЕ СРАВНЕНИЕ: ФАЙЛ ПРИЛОЖЕНИЯ vs НАШИ ДАННЫЕ (АВГУСТ 2026)")
print("=" * 100)

print(f"\n{'Показатель':<35} {'Приложение':>15} {'Наше':>15} {'Δ':>12} {'%':>8} {'Метод':<30}")
print("-" * 120)

for name, app_val in APP.items():
    our_val = OUR.get(name, 0)
    delta = our_val - app_val
    pct = (delta / abs(app_val) * 100) if app_val else 0

    # Определяем статус
    if abs(delta) < 100:
        mark = "✅"
    elif abs(delta) < 1000:
        mark = "⚠️"
    elif abs(delta) < 5000:
        mark = "🟡"
    else:
        mark = "❌"

    # Метод
    method = ""
    if name == "Выручка от реализации":
        method = "sale_price"
    elif name == "Баллы за скидки":
        method = "bonus"
    elif name == "Программы партнёров":
        method = "coinvestment"
    elif name == "Комиссия Ozon":
        method = "sale_commission"
    elif name == "Налоги (7%)":
        method = "7% (приложение)"
    elif name == "Налоги (15%)":
        method = "15% (правильная)"
    elif "Логистика продаж" in name:
        method = "Logistic + DeliveryToHandover"
    elif name == "Логистика отмен и возвратов":
        method = "ReturnFlowLogistic"

    print(f"{mark} {name:<33} {app_val:>15,.2f} {our_val:>15,.2f} {delta:>+12,.2f} {pct:>+7.1f}% {method:<30}")

print("\n" + "=" * 100)
print("ЧЕГО У НАС НЕТ (нужно найти)")
print("=" * 100)

# Проверяем, что может быть не найдено
not_found = []
if advertising == 0 and APP["Реклама и ДРР"] != 0:
    not_found.append(f"Реклама и ДРР: {APP['Реклама и ДРР']} ₽ (в приложении)")

# Проверяем типы услуг, которые мы не классифицировали
classified_ids = set()
for tid in [32, 59, 98, 29, 31, 28]:  # логистика
    classified_ids.add(tid)
for tid in [1, 74, 3, 79, 63, 66]:  # агенты
    classified_ids.add(tid)
for tid in [71, 46, 76, 21, 73]:  # FBO
    classified_ids.add(tid)
for tid in [93, 89, 90, 91, 92, 94, 14, 45]:  # штрафы
    classified_ids.add(tid)
for tid in [10, 25, 104]:  # компенсации
    classified_ids.add(tid)
for tid in [18, 20, 23, 41, 33, 54, 19, 47, 48, 49, 50, 51, 52]:  # прочие
    classified_ids.add(tid)

unclassified = []
for tid, (name, total) in services.items():
    if tid not in classified_ids:
        unclassified.append((tid, name, total))

if unclassified:
    print("\nНе классифицированные типы услуг:")
    for tid, name, total in unclassified:
        print(f"  {tid:<5} {name:<40} {total:>12,.2f}")

if not_found:
    print("\nНе найдены в API:")
    for x in not_found:
        print(f"  • {x}")

print("\n" + "=" * 100)
print("ИТОГИ")
print("=" * 100)
print(f"""
  Выручка:     наше {app_revenue:>12,.2f}  приложение {APP['Выручка суммарно']:>12,.2f}  Δ {app_revenue - APP['Выручка суммарно']:>+10,.2f}
  Расходы:     наше {-expenses_total:>12,.2f}  приложение {APP['Расходы']:>12,.2f}  Δ {-expenses_total - APP['Расходы']:>+10,.2f}
  Себестоимость: наше {cogs:>10,.2f}  приложение {APP['Себестоимость']:>12,.2f}  Δ {cogs - APP['Себестоимость']:>+10,.2f}
  Маржа:       наше {margin:>12,.2f}  приложение {APP['Маржа']:>12,.2f}  Δ {margin - APP['Маржа']:>+10,.2f}
  Налог 15%:   наше {tax_15:>12,.2f}
  Налог 7%:    наше {tax_7:>12,.2f}  приложение {APP['Налоги (7%)']:>12,.2f}  Δ {tax_7 - APP['Налоги (7%)']:>+10,.2f}
  Чистая:      наше {net_15:>12,.2f}  приложение {APP['Чистая прибыль (7%)']:>12,.2f}
""")

con.close()
