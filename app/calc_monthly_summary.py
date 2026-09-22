"""
calc_monthly_summary.py - свод финансов за месяц.
Собирает все данные из БД и сравнивает с приложением.
"""
import os
import sqlite3
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
TAX_RATE = 0.15  # УСН 15%


def money(x):
    return f"{x:>14,.2f} ₽"


def main():
    import sys
    month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"

    # Границы месяца
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

    # === 1. Выручка (из sales_daily) ===
    r = con.execute("""
        SELECT COUNT(*) AS n, SUM(revenue) AS rev, SUM(orders_units) AS orders
        FROM sales_daily
        WHERE date >= ? AND date < ?
    """, (date_from, date_to)).fetchone()
    revenue = r["rev"] or 0
    orders = r["orders"] or 0

    # === 2. Комиссии и баллы (из accruals) ===
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

    # === 3. Услуги (из accruals_services) ===
    s = con.execute("""
        SELECT SUM(amount) AS total FROM accruals_services
        WHERE date >= ? AND date < ?
    """, (date_from, date_to)).fetchone()
    services_total = s["total"] or 0

    # Услуги по типам
    services_by_type = {}
    for row in con.execute("""
        SELECT type_name, SUM(amount) AS total, COUNT(*) AS n
        FROM accruals_services
        WHERE date >= ? AND date < ?
        GROUP BY type_name
        ORDER BY ABS(SUM(amount)) DESC
    """, (date_from, date_to)):
        services_by_type[row["type_name"]] = row["total"]

    # === 4. Себестоимость — по ДОСТАВЛЕННЫМ ===
    cogs = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.delivered) AS delivered
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs += (row[0] or 0) * (row[1] or 0)

    # Для сравнения — себестоимость по заказам
    cogs_orders = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs_orders += (row[0] or 0) * (row[1] or 0)

    # И по выкупленным
    cogs_purchased = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.purchased) AS purchased
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs_purchased += (row[0] or 0) * (row[1] or 0)

    # === 5. Расчёты ===
    # Выручка приложения = sale_price + bonus + coinvestment
    # (то есть "что заплатил покупатель" + "баллы за скидки" + "партнёры")
    app_revenue = sale_price + bonus + coinvestment

    # Расходы = комиссия + услуги
    expenses = abs(commission) + abs(services_total)

    # Маржа = выручка − расходы − себестоимость
    margin = app_revenue - expenses - cogs

    # Налоговая база = выручка − баллы
    tax_base = app_revenue - bonus
    tax_15 = tax_base * TAX_RATE

    # Чистая прибыль = маржа − налог
    net_profit = margin - tax_15

    # === 6. Вывод ===
    print(f"\n[1] ВЫРУЧКА")
    print(f"    Sale price (покупатели):       {money(sale_price)}")
    print(f"    + Баллы за скидки:             {money(bonus)}")
    print(f"    + Партнёры:                    {money(coinvestment)}")
    print(f"    = ВЫРУЧКА:                     {money(app_revenue)}")
    print(f"    (заказов: {orders})")

    print(f"\n[2] РАСХОДЫ")
    print(f"    Гросс-комиссия:                {money(commission)}")
    print(f"    Эффективная комиссия:          {money(commission + bonus + coinvestment)}")
    print(f"    Услуги Ozon:                   {money(services_total)}")
    print(f"    ─────────────────────────────────")
    print(f"    Всего расходы:                 {money(expenses)}")

    print(f"\n[3] ДЕТАЛИЗАЦИЯ УСЛУГ")
    if services_by_type:
        for name, total in sorted(services_by_type.items(), key=lambda x: -abs(x[1]))[:12]:
            print(f"    {name:<38} {money(total)}")
    else:
        print("    Нет данных")

    print(f"\n[4] СЕБЕСТОИМОСТЬ И МАРЖА")
    print(f"    COGS по заказам (orders):      {money(cogs_orders)}")
    print(f"    COGS по доставленным:          {money(cogs)}")
    print(f"    COGS по выкупленным:           {money(cogs_purchased)}")
    print(f"    ⭐ Используем (доставлено):    {money(cogs)}")
    print(f"    Маржа = Выручка − Расходы − Себест")
    print(f"          = {app_revenue:,.0f} − {expenses:,.0f} − {cogs:,.0f}")
    print(f"          = {money(margin)}")

    print(f"\n[5] НАЛОГИ")
    print(f"    Налоговая база (Выручка − Баллы): {money(tax_base)}")
    print(f"    Налог УСН 15%:                 {money(tax_15)}")

    print(f"\n[6] ЧИСТАЯ ПРИБЫЛЬ")
    print(f"    Маржа − Налог:                 {money(net_profit)}")

    # === Сравнение с приложением ===
    targets = {
        "Выручка": 302967,
        "Комиссия Ozon": -151050.09,
        "Баллы": 139902.77,
        "Партнёры": 1681.27,
        "Себестоимость": 111319,
        "Маржа": 15629.34,
        "Налог 7%": 11414.50,
        "Чистая (7%)": 4214.84,
        "Чистая (15%)": -8831,
    }

    print(f"\n[7] СРАВНЕНИЕ С ПРИЛОЖЕНИЕМ")
    print(f"    {'Метрика':<25} {'Наше':>14} {'Приложение':>14} {'Δ':>12}")
    print("    " + "-" * 70)
    our = {
        "Выручка": app_revenue,
        "Комиссия Ozon": commission,
        "Баллы": bonus,
        "Партнёры": coinvestment,
        "Себестоимость": cogs,
        "Маржа": margin,
        "Чистая (15%)": net_profit,
    }
    for name, app_val in targets.items():
        our_val = our.get(name, 0)
        delta = our_val - app_val
        print(f"    {name:<25} {our_val:>14,.2f} {app_val:>14,.2f} {delta:>+12,.2f}")

    # Сохраняем в monthly_reports
    try:
        con.execute("""
            UPDATE monthly_reports
            SET net_profit = ?, tax_15 = ?, tax_base = ?, fetched_at = ?
            WHERE month = ?
        """, (net_profit, tax_15, tax_base,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), month))
        con.commit()
        print(f"\n[OK] monthly_reports обновлён для {month}")
    except Exception as e:
        print(f"[WARN] Не удалось сохранить: {e}")

    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
