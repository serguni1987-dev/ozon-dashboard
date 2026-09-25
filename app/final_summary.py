"""
final_summary.py - полный свод P&L с эталоном и поиском расхождений.
Пробует разные источники для выручки, чтобы найти 100% совпадение.
"""
import os
import json
import requests
import sqlite3
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
load_dotenv(os.path.join(APP_DIR, ".env"))

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}

date_from, date_to = "2026-08-01", "2026-09-01"

# ЭТАЛОН из приложения
ETALON = {
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
    "Реклама": 291.75,
    "Себестоимость": 111319.00,
    "Маржа": 15629.34,
    "Налог 15%": 24459.63,
    "Чистая": -8830.29,
}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def f(v):
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def sum_block(rows, block, field):
    total = 0.0
    for row in rows:
        b = row.get(block) or {}
        total += f(b.get(field))
    return total


# === ЗАПРАШИВАЕМ realization заново ===
print("=" * 100)
print("ЗАПРАШИВАЕМ /v2/finance/realization ЗА АВГУСТ")
print("=" * 100)

r = requests.post(
    "https://api-seller.ozon.ru/v2/finance/realization",
    headers=H,
    json={"month": 8, "year": 2026},
    timeout=120,
)
data = r.json()
result = data.get("result") or {}
rows = result.get("rows") or []

delivery = [x for x in rows if x.get("delivery_commission")]
returns = [x for x in rows if x.get("return_commission")]

print(f"Строк: {len(rows)} (delivery: {len(delivery)}, return: {len(returns)})")

# Считаем delivery и return отдельно
d_amount = sum_block(delivery, "delivery_commission", "amount")
d_bonus = sum_block(delivery, "delivery_commission", "bonus")
d_std = sum_block(delivery, "delivery_commission", "standard_fee")
d_total = sum_block(delivery, "delivery_commission", "total")
d_coinv = sum_block(delivery, "delivery_commission", "bank_coinvestment") + \
          sum_block(delivery, "delivery_commission", "pick_up_point_coinvestment")

r_amount = sum_block(returns, "return_commission", "amount")
r_bonus = sum_block(returns, "return_commission", "bonus")
r_std = sum_block(returns, "return_commission", "standard_fee")
r_total = sum_block(returns, "return_commission", "total")
r_coinv = sum_block(returns, "return_commission", "bank_coinvestment") + \
          sum_block(returns, "return_commission", "pick_up_point_coinvestment")

print(f"\nDELIVERY:")
print(f"  amount:       {d_amount:>14,.2f}")
print(f"  bonus:        {d_bonus:>14,.2f}")
print(f"  standard_fee: {d_std:>14,.2f}")
print(f"  total:        {d_total:>14,.2f}")
print(f"  coinv:        {d_coinv:>14,.2f}")

print(f"\nRETURN:")
print(f"  amount:       {r_amount:>14,.2f}")
print(f"  bonus:        {r_bonus:>14,.2f}")
print(f"  standard_fee: {r_std:>14,.2f}")
print(f"  total:        {r_total:>14,.2f}")
print(f"  coinv:        {r_coinv:>14,.2f}")

# === ПРОВЕРКА ФОРМУЛЫ ===
print("\n" + "=" * 100)
print("ПОИСК ПРАВИЛЬНОЙ ФОРМУЛЫ (совпадение с эталоном)")
print("=" * 100)

print(f"\n{'Метрика':<25} {'delivery':>14} {'del-ret':>14} {'Эталон':>14}")
print("-" * 70)

checks = [
    ("amount", d_amount, d_amount - r_amount, ETALON["Выручка от реализации"]),
    ("bonus", d_bonus, d_bonus - r_bonus, ETALON["Баллы за скидки"]),
    ("coinvestment", d_coinv, d_coinv - r_coinv, ETALON["Программы партнёров"]),
    ("standard_fee", d_std, d_std - r_std, ETALON["Комиссия Ozon"]),
]

for name, dv, dr, target in checks:
    mark_dv = "✅" if abs(dv - target) < 1 else "  "
    mark_dr = "✅" if abs(dr - target) < 1 else "  "
    print(f"{name:<25} {dv:>14,.2f} {dr:>14,.2f} {target:>14,.2f}  dv:{mark_dv} dr:{mark_dr}")

# === СВОД ===
print("\n" + "=" * 100)
print("СВОД P&L — все источники")
print("=" * 100)

# Из accruals для услуг
services = {}
for row in con.execute("""
    SELECT type_id, SUM(amount) AS total
    FROM accruals_services WHERE date >= ? AND date < ?
    GROUP BY type_id
""", (date_from, date_to)):
    services[row["type_id"]] = abs(f(row["total"]))

def s(*tids):
    return sum(services.get(t, 0) for t in tids)

logist = s(32, 59, 98)
agents = s(1, 74, 79)
fbo = s(71, 46, 76)
other = s(93, 45)
misc = s(18, 20)
ads = s(3)

# Себестоимость — варианты
cogs_dlv = f(con.execute("""
    SELECT SUM(p.cost_price * sd.delivered)
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
""", (date_from, date_to)).fetchone()[0])

cogs_ord = f(con.execute("""
    SELECT SUM(p.cost_price * sd.orders_units)
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
""", (date_from, date_to)).fetchone()[0])

cogs_pur = f(con.execute("""
    SELECT SUM(p.cost_price * sd.purchased)
    FROM sales_daily sd JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= ? AND sd.date < ?
""", (date_from, date_to)).fetchone()[0])

# Свод
OUR = {
    "Выручка от реализации": d_amount - r_amount,
    "Баллы за скидки": d_bonus - r_bonus,
    "Программы партнёров": d_coinv - r_coinv,
    "Комиссия Ozon": d_std - r_std,
    "Логистика": logist,
    "Услуги агентов": agents,
    "Услуги FBO": fbo,
    "Другие услуги": other,
    "Компенсации": 0,
    "Прочие начисления": misc,
    "Реклама": ads,
}

OUR["Выручка"] = OUR["Выручка от реализации"] + OUR["Баллы за скидки"] + OUR["Программы партнёров"]
OUR["Себестоимость_dlv"] = cogs_dlv
OUR["Себестоимость_ord"] = cogs_ord
OUR["Себестоимость_pur"] = cogs_pur

print(f"\n{'Метрика':<28} {'Наше':>14} {'Эталон':>14} {'Δ':>12} {'%':>8} {'Статус'}")
print("-" * 100)

ok = warn = err = 0
for name, et in ETALON.items():
    if name in ["Маржа", "Налог 15%", "Чистая"]:
        continue
    if name == "Себестоимость":
        val = cogs_dlv  # основной вариант
    else:
        val = OUR.get(name, 0)

    delta = val - et
    pct = (delta / abs(et) * 100) if et else 0

    if abs(delta) < 1:
        mark = "✅ точно"
        ok += 1
    elif abs(delta) < 100:
        mark = "✅ близко"
        ok += 1
    elif abs(delta) < 1000:
        mark = "⚠️"
        warn += 1
    else:
        mark = "❌"
        err += 1

    print(f"{name:<28} {val:>14,.2f} {et:>14,.2f} {delta:>+12,.2f} {pct:>+7.1f}% {mark}")

# === ПРОБУЕМ РАЗНЫЕ СЕБЕСТОИМОСТИ ===
print("\n" + "=" * 100)
print("ПОИСК СЕБЕСТОИМОСТИ = 111 319")
print("=" * 100)

target = 111319.00
print(f"\n  delivered × cost:   {cogs_dlv:>14,.2f}  Δ {cogs_dlv - target:>+12,.2f}")
print(f"  orders × cost:      {cogs_ord:>14,.2f}  Δ {cogs_ord - target:>+12,.2f}")
print(f"  purchased × cost:   {cogs_pur:>14,.2f}  Δ {cogs_pur - target:>+12,.2f}")

# Может быть cost_price × delivered только по SKU из realization
real_skus = list(set(
    row["sku"] for row in con.execute("""
        SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = '2026-08'
    """)
))
if real_skus:
    q = ",".join("?" * len(real_skus))
    cogs_real = f(con.execute(f"""
        SELECT SUM(p.cost_price * sd.delivered)
        FROM sales_daily sd JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
          AND p.sku IN ({q})
    """, (date_from, date_to, *real_skus)).fetchone()[0])
    print(f"  delivered × cost (только realization SKU): {cogs_real:>14,.2f}  Δ {cogs_real - target:>+12,.2f}")

# === МАРЖА И ЧИСТАЯ ===
print("\n" + "=" * 100)
print("РАСЧЁТ МАРЖИ И ЧИСТОЙ")
print("=" * 100)

revenue = OUR["Выручка"]
expenses = OUR["Комиссия Ozon"] + OUR["Логистика"] + OUR["Услуги агентов"] + \
           OUR["Услуги FBO"] + OUR["Другие услуги"] + OUR["Прочие начисления"] + OUR["Реклама"]

margin = revenue - expenses - cogs_dlv
tax_base = revenue - OUR["Баллы за скидки"]
tax = tax_base * 0.15
net = margin - tax

print(f"\n  Выручка:      {revenue:>14,.2f}")
print(f"  − Расходы:   -{expenses:>14,.2f}")
print(f"  − Себест:    -{cogs_dlv:>14,.2f}")
print(f"  = Маржа:      {margin:>14,.2f}   (эталон: {ETALON['Маржа']:,.2f})")
print(f"\n  База налога:  {tax_base:>14,.2f}")
print(f"  Налог 15%:   -{tax:>14,.2f}   (эталон: {ETALON['Налог 15%']:,.2f})")
print(f"  Чистая:       {net:>14,.2f}   (эталон: {ETALON['Чистая']:,.2f})")

print(f"\n" + "=" * 100)
print(f"ИТОГО: OK={ok}, WARN={warn}, ERR={err}")
print("=" * 100)

con.close()
