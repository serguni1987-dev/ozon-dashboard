"""
full_audit.py - построчная сверка ВСЕХ значений из файла и API.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

# Все значения из файла приложения (август 2026)
FILE = {
    # Сводка
    "Выручка суммарно": 302967.00,
    "Выручка от реализации": 161382.96,
    "Баллы за скидки": 139902.77,
    "Программы партнёров": 1681.27,
    "Расходы (всего)": 175726.91,
    "Реклама и ДРР": 291.75,
    "Себестоимость": 111319.00,
    "Маржа": 15629.34,
    "Доп. расходы": 0.00,
    "Налоги": 11414.50,
    "Чистая прибыль": 4214.84,
    "Рентабельность %": 1.4,
    # Детализация расходов
    "Комиссия Ozon": 151050.09,
    "Логистика": 9850.00,
    "Услуги агентов": 9028.22,
    "Услуги FBO": 721.00,
    "Другие услуги и штрафы": 391.50,
    "Компенсации": 0.00,
    "Прочие начисления": 4686.10,
    # Детализация логистики
    "Логистика продаж": 8705.00,
    "Логистика отмен и возвратов": 1145.00,
    # Налоги
    "Налогооблогаемая база": 163064.23,
    "Налоговая ставка %": 7.0,
}

# Данные из БД
date_from = "2026-08-01"
date_to = "2026-09-01"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# 1. accruals
a = con.execute("""
    SELECT SUM(sale_price) AS slp, SUM(sale_commission) AS comm,
           SUM(bonus) AS bonus, SUM(coinvestment) AS coinv,
           SUM(seller_price) AS sp
    FROM accruals WHERE date >= ? AND date < ?
""", (date_from, date_to)).fetchone()
sale_price = a["slp"] or 0
commission = abs(a["comm"] or 0)
bonus = a["bonus"] or 0
coinvestment = a["coinv"] or 0
seller_price = a["sp"] or 0
revenue = sale_price + bonus + coinvestment

# 2. Услуги по type_id
services = {}
for r in con.execute("""
    SELECT type_id, type_name, SUM(amount) AS total, COUNT(*) AS n
    FROM accruals_services WHERE date >= ? AND date < ?
    GROUP BY type_id, type_name
    ORDER BY ABS(SUM(amount)) DESC
""", (date_from, date_to)):
    services[r["type_id"]] = {
        "name": r["type_name"],
        "total": abs(r["total"]),
        "n": r["n"],
    }

# 3. Категории
def s(*tids):
    return sum(services.get(t, {}).get("total", 0) for t in tids)

logist_sales = s(32, 98)
logist_returns = s(59)
logist_other = s(29)
logist_total = logist_sales + logist_returns + logist_other

agents = s(1, 74, 79)
fbo = s(71, 46)
other_serv = s(93, 45)
comp = s(10, 25, 104)
misc = s(18, 20)
ads = s(3)

services_total = logist_total + agents + fbo + other_serv + comp + misc + ads
expenses = commission + services_total

# 4. Себестоимость
cogs = 0.0
for row in con.execute("""
    SELECT p.cost_price, SUM(sd.delivered) AS d
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
    GROUP BY p.sku
""", (date_from, date_to)):
    cogs += (row[0] or 0) * (row[1] or 0)

# 5. Расчёты
margin = revenue - expenses - cogs
tax_base = revenue - bonus
tax_7 = tax_base * 0.07
tax_15 = tax_base * 0.15
net_7 = margin - tax_7
net_15 = margin - tax_15

# Наши значения (все)
API = {
    "Выручка суммарно": revenue,
    "Выручка от реализации": sale_price,
    "Баллы за скидки": bonus,
    "Программы партнёров": coinvestment,
    "Расходы (всего)": expenses,
    "Реклама и ДРР": ads,
    "Себестоимость": cogs,
    "Маржа": margin,
    "Доп. расходы": 0.00,
    "Налоги": tax_15,
    "Чистая прибыль": net_15,
    "Рентабельность %": (net_15 / revenue * 100) if revenue else 0,
    "Комиссия Ozon": commission,
    "Логистика": logist_total,
    "Услуги агентов": agents,
    "Услуги FBO": fbo,
    "Другие услуги и штрафы": other_serv,
    "Компенсации": comp,
    "Прочие начисления": misc,
    "Логистика продаж": logist_sales,
    "Логистика отмен и возвратов": logist_returns,
    "Налогооблогаемая база": tax_base,
    "Налоговая ставка %": 15.0,
}

# Источник (откуда берём)
SOURCE = {
    "Выручка суммарно": "accruals",
    "Выручка от реализации": "accruals.sale_price",
    "Баллы за скидки": "accruals.bonus",
    "Программы партнёров": "accruals.coinvestment",
    "Расходы (всего)": "комис + услуги",
    "Реклама и ДРР": "type_3",
    "Себестоимость": "sales_daily.delivered",
    "Маржа": "расчёт",
    "Доп. расходы": "нет",
    "Налоги": "УСН 15%",
    "Чистая прибыль": "расчёт",
    "Рентабельность %": "расчёт",
    "Комиссия Ozon": "accruals.sale_commission",
    "Логистика": "type 32+59+98",
    "Услуги агентов": "type 1+74+79",
    "Услуги FBO": "type 71+46",
    "Другие услуги и штрафы": "type 93+45",
    "Компенсации": "type 10+25+104",
    "Прочие начисления": "type 18+20",
    "Логистика продаж": "type 32+98",
    "Логистика отмен и возвратов": "type 59",
    "Налогооблогаемая база": "revenue - bonus",
    "Налоговая ставка %": "УСН",
}

# Вывод
print("=" * 130)
print("ПОЛНАЯ СВЕРКА: ФАЙЛ ПРИЛОЖЕНИЯ vs API OZON (АВГУСТ 2026)")
print("=" * 130)

print()
print(f"{'Показатель':<28} {'Файл':>14} {'Наше (API)':>14} {'Δ':>12} {'%':>8} {'Статус':<10} {'Метод':<30}")
print("-" * 130)

ok_count = 0
warn_count = 0
err_count = 0
missing_count = 0

for name, file_val in FILE.items():
    api_val = API.get(name, 0)
    delta = api_val - file_val
    pct = (delta / abs(file_val) * 100) if file_val else 0

    if abs(delta) < 1:
        mark = "OK точн"
        ok_count += 1
    elif abs(delta) < 100:
        mark = "OK близко"
        ok_count += 1
    elif abs(delta) < 1000:
        mark = "~"
        warn_count += 1
    elif abs(delta) < 10000:
        mark = "??"
        warn_count += 1
    else:
        mark = "X"
        err_count += 1

    src = SOURCE.get(name, "-")
    print(f"{name:<28} {file_val:>14,.2f} {api_val:>14,.2f} {delta:>+12,.2f} {pct:>+7.1f}% {mark:<10} {src:<30}")

print()
print("=" * 130)
print(f"ИТОГО: OK: {ok_count}, WARN: {warn_count}, ERR: {err_count}")
print("=" * 130)

# Разбор неклассифицированных услуг
print()
print("=" * 130)
print("ВСЕ УСЛУГИ ИЗ accruals_services (проверка полноты)")
print("=" * 130)
print()
print(f"{'Type ID':<8} {'Название':<40} {'Сумма':>14} {'Записей':>8}")
print("-" * 75)
for tid in sorted(services.keys(), key=lambda k: -services[k]["total"]):
    info = services[tid]
    print(f"{tid:<8} {info['name']:<40} {info['total']:>14,.2f} {info['n']:>8}")

# Проверяем неклассифицированные
classified = {1, 3, 18, 20, 25, 32, 46, 59, 71, 74, 79, 93, 98, 10, 29, 45, 104}
unclassified = [t for t in services.keys() if t not in classified]

if unclassified:
    print()
    print("НЕ КЛАССИФИЦИРОВАНЫ:")
    for t in unclassified:
        print(f"  type_{t}: {services[t]['name']} = {services[t]['total']:,.2f}")
else:
    print()
    print("Все услуги классифицированы")

con.close()
