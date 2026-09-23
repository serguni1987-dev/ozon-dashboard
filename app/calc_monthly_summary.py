"""
calc_monthly_summary.py - свод финансов за месяц.
Группирует услуги по категориям приложения (по type_id).
"""
import os
import sqlite3
import sys
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
TAX_RATE = 0.15


# Маппинг type_id → категория приложения
CATEGORY_MAP = {
    # Логистика
    32:  "Логистика",      # Logistic
    59:  "Логистика",      # ReturnFlowLogistic
    98:  "Логистика",      # DeliveryToHandoverPlaceByOzon
    29:  "Логистика",      # LastMileCourier
    31:  "Логистика",      # LastMile
    28:  "Логистика",      # LastMileCourier (alt)

    # Услуги агентов
    1:   "Услуги агентов", # Acquiring
    74:  "Услуги агентов", # StarsMembership
    3:   "Услуги агентов", # BrandCommission
    79:  "Услуги агентов", # TemporaryPlacementsAgent
    63:  "Услуги агентов", # RfbsDomesticAgentFee
    66:  "Услуги агентов", # RfbsGlobalAgentFee

    # Услуги FBO
    71:  "Услуги FBO",     # SellerReturns
    46:  "Услуги FBO",     # Placements
    76:  "Услуги FBO",     # StockInsurance
    21:  "Услуги FBO",     # Fulfillment
    73:  "Услуги FBO",     # Shipment

    # Другие услуги и штрафы
    93:  "Другие услуги",  # DefectFineErrors
    89:  "Другие услуги",  # DefectFineModeration
    90:  "Другие услуги",  # DefectFineProhibitedGoods
    91:  "Другие услуги",  # DefectFineCounterfeitGoods
    92:  "Другие услуги",  # DefectFineComplaint
    94:  "Другие услуги",  # DefectFineShipmentDelayRate
    14:  "Другие услуги",  # DefectRate
    45:  "Другие услуги",  # PickUpPointReturnAcceptance

    # Компенсации
    10:  "Компенсации",    # Compensation
    25:  "Компенсации",    # ItemCompensation
    104: "Компенсации",    # B2CInsuranceCompensation

    # Прочие начисления
    18:  "Прочие",         # EarlyPayment
    20:  "Прочие",         # FlexiblePayments
    23:  "Прочие",         # InternetSiteAdvertising
    41:  "Прочие",         # PayPerClick
    33:  "Прочие",         # Marketing
    54:  "Прочие",         # Promotion
    19:  "Прочие",         # ExternalPromotion
    47:  "Прочие",         # PointsForReviews
    48:  "Прочие",         # PremiumCashbackIndividualPoints
    49:  "Прочие",         # PremiumCashbackPromotion
    50:  "Прочие",         # PremiumMailingCommission
    51:  "Прочие",         # PremiumMembership
    52:  "Прочие",         # PremiumSubscription
}


def money(x):
    return f"{x:>14,.2f} ₽"


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    y, m = month.split("-")
    y, m = int(y), int(m)
    if m == 12:
        next_y, next_m = y + 1, 1
    else:
        next_y, next_m = y, m + 1
    date_from = f"{y}-{m:02d}-01"
    date_to = f"{next_y}-{next_m:02d}-01"

    print("=" * 80)
    print(f"СВОД ФИНАНСОВ ЗА {month}")
    print("=" * 80)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # === 1. Выручка и комиссия из accruals ===
    a = con.execute("""
        SELECT COUNT(*) AS n,
               SUM(seller_price) AS sp,
               SUM(sale_price) AS slp,
               SUM(sale_commission) AS comm,
               SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv
        FROM accruals
        WHERE date >= ? AND date < ?
    """, (date_from, date_to)).fetchone()
    seller_price = a["sp"] or 0
    sale_price = a["slp"] or 0
    commission = a["comm"] or 0
    bonus = a["bonus"] or 0
    coinvestment = a["coinv"] or 0

    # === 2. Услуги по категориям ===
    cats = {
        "Логистика": 0.0,
        "Услуги агентов": 0.0,
        "Услуги FBO": 0.0,
        "Другие услуги": 0.0,
        "Компенсации": 0.0,
        "Прочие": 0.0,
        "Без категории": 0.0,
    }
    services_detail = {}

    for r in con.execute("""
        SELECT type_id, type_name, SUM(amount) AS total
        FROM accruals_services
        WHERE date >= ? AND date < ?
        GROUP BY type_id, type_name
    """, (date_from, date_to)):
        tid = r["type_id"]
        cat = CATEGORY_MAP.get(tid, "Без категории")
        cats[cat] += r["total"]
        services_detail[tid] = (r["type_name"], r["total"], cat)

    # === 3. Себестоимость ===
    cogs = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.delivered) AS delivered
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs += (row[0] or 0) * (row[1] or 0)

    cogs_orders = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs_orders += (row[0] or 0) * (row[1] or 0)

    # === 4. Расчёты ===
    app_revenue = sale_price + bonus + coinvestment
    services_total = sum(cats.values())
    expenses = abs(commission) + abs(services_total)
    margin = app_revenue - expenses - cogs

    tax_base = app_revenue - bonus
    tax_15 = tax_base * TAX_RATE
    net_profit = margin - tax_15

    # === 5. Вывод ===
    print(f"\n[1] ВЫРУЧКА")
    print(f"    Sale price:                    {money(sale_price)}")
    print(f"    + Баллы за скидки:             {money(bonus)}")
    print(f"    + Партнёры:                    {money(coinvestment)}")
    print(f"    = ВЫРУЧКА:                     {money(app_revenue)}")

    print(f"\n[2] РАСХОДЫ")
    print(f"    Гросс-комиссия:                {money(commission)}")
    print(f"    Логистика:                     {money(cats['Логистика'])}")
    print(f"    Услуги агентов:                {money(cats['Услуги агентов'])}")
    print(f"    Услуги FBO:                    {money(cats['Услуги FBO'])}")
    print(f"    Другие услуги и штрафы:        {money(cats['Другие услуги'])}")
    print(f"    Компенсации:                   {money(cats['Компенсации'])}")
    print(f"    Прочие начисления:             {money(cats['Прочие'])}")
    print(f"    Без категории:                 {money(cats['Без категории'])}")
    print(f"    ─────────────────────────────────")
    print(f"    Всего услуги:                  {money(services_total)}")

    print(f"\n[3] ДЕТАЛИЗАЦИЯ ПО TYPE_ID")
    print(f"    {'ID':<5} {'Название':<35} {'Категория':<18} {'Сумма':>12}")
    print("    " + "-" * 72)
    for tid in sorted(services_detail.keys(),
                     key=lambda k: -abs(services_detail[k][1])):
        name, total, cat = services_detail[tid]
        print(f"    {tid:<5} {name:<35} {cat:<18} {total:>12,.2f}")

    print(f"\n[4] СЕБЕСТОИМОСТЬ")
    print(f"    По доставленным:               {money(cogs)}")
    print(f"    По заказам (для справки):      {money(cogs_orders)}")

    print(f"\n[5] НАЛОГИ")
    print(f"    Налоговая база:                {money(tax_base)}")
    print(f"    Налог УСН 15%:                 {money(tax_15)}")

    print(f"\n[6] ИТОГО")
    print(f"    Выручка − Расходы − Себест:    {money(margin)}")
    print(f"    Маржа:                         {money(margin)}")
    print(f"    − Налог:                       {money(tax_15)}")
    print(f"    = ЧИСТАЯ ПРИБЫЛЬ:              {money(net_profit)}")

    # === 6. Сравнение с приложением ===
    targets = {
        "Выручка": 302967,
        "Комиссия Ozon": -151050.09,
        "Логистика": -9850,
        "Услуги агентов": -9028.22,
        "Услуги FBO": -721,
        "Другие услуги": -391.5,
        "Компенсации": 0,
        "Прочие": -4686.1,
        "Себестоимость": -111319,
        "Маржа": 15629.34,
        "Чистая (15%)": -8831,
    }

    ours = {
        "Выручка": app_revenue,
        "Комиссия Ozon": commission,
        "Логистика": cats["Логистика"],
        "Услуги агентов": cats["Услуги агентов"],
        "Услуги FBO": cats["Услуги FBO"],
        "Другие услуги": cats["Другие услуги"],
        "Компенсации": cats["Компенсации"],
        "Прочие": cats["Прочие"],
        "Себестоимость": -cogs,
        "Маржа": margin,
        "Чистая (15%)": net_profit,
    }

    print(f"\n[7] СРАВНЕНИЕ С ПРИЛОЖЕНИЕМ")
    print(f"    {'Метрика':<22} {'Наше':>14} {'Приложение':>14} {'Δ':>12}")
    print("    " + "-" * 65)
    for name, app_val in targets.items():
        our_val = ours.get(name, 0)
        delta = our_val - app_val
        mark = "✅" if abs(delta) < 500 else "⚠" if abs(delta) < 5000 else "❌"
        print(f"    {name:<22} {our_val:>14,.2f} {app_val:>14,.2f} {delta:>+12,.2f} {mark}")

    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
