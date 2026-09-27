"""
calc_capital.py — блок КАПИТАЛ: где деньги, что забрать.

Считает 4 подблока:
  1. ГДЕ ДЕНЬГИ
  2. ЧТО ЗАБРАТЬ
  3. КАССОВЫЙ ПРОГНОЗ (14 дней)
  4. ОБОРОТ ДЕНЕГ
"""
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"
TAX_RATE = 0.15           # УСН 15%
RESERVE_PROCUREMENT = 0.10  # 10% выручки на закупки
RESERVE_FINES = 0.05       # 5% на штрафы/риски


def money(x):
    return f"{x:>12,.0f} ₽"


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    print("=" * 80)
    print(f"КАПИТАЛ — расчёт на {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 80)

    # === 1. ГДЕ ДЕНЬГИ ===
    print("\n[1] ГДЕ ДЕНЬГИ")

    # 1.1. На счету — из ручного ввода (последняя запись)
    row = con.execute("""
        SELECT update_date, on_account FROM capital_input
        ORDER BY update_date DESC LIMIT 1
    """).fetchone()
    if row:
        on_account = row["on_account"]
        on_account_date = row["update_date"]
        days_old = (datetime.now() - datetime.strptime(on_account_date, "%Y-%m-%d")).days
        print(f"  На счету:               {money(on_account)}  (обновлено {on_account_date}, {days_old} дн назад)")
    else:
        on_account = 0
        on_account_date = None
        print(f"  На счету:               {money(0)}  (нет данных — заполни лист ВВОД)")

    # 1.2. У Ozon к выплате — ТОЧНО из balance_history (API)
    bh = con.execute("""
        SELECT fetched_at, closing_balance, accrued, payments, date_from, date_to
        FROM balance_history
        ORDER BY fetched_at DESC LIMIT 1
    """).fetchone()

    if bh:
        owed_by_ozon = bh[1] or 0
        bh_fetched = bh[0]
        bh_accrued = bh[2] or 0
        bh_payments = bh[3] or 0
        bh_from = bh[4]
        bh_to = bh[5]
        print(f"  У Ozon к выплате:       {money(owed_by_ozon)}")
        print(f"    (точно из API, обновлено {bh_fetched[:16]})")
        print(f"    период: {bh_from} — {bh_to}")
        print(f"    начислено: {money(bh_accrued)}, выплачено: {money(bh_payments)}")
    else:
        owed_by_ozon = 0
        print(f"  У Ozon к выплате:       {money(0)}  (запусти py fetch_balance.py)")

    # 1.3. В товаре на складе
    frozen = con.execute("""
        SELECT SUM(cs.total_present * p.cost_price)
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        WHERE p.cost_price > 0 AND cs.total_present > 0
    """).fetchone()[0] or 0
    print(f"  В товаре на складе:     {money(frozen)}")

    # 1.4. В товаре в пути (пока нет данных — заглушка)
    in_transit = 0
    print(f"  В товаре в пути:        {money(in_transit)}  (нет данных — нужно из API)")

    # 1.5. Резерв налога УСН 15%
    # Налог считается от прибыли. Прибыль за 30 дней ≈ из sales_daily
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    # Упрощённый расчёт прибыли за последние 30 дней
    # (в реальности у нас есть profit из daily_dashboard)
    revenue_30 = con.execute(
        "SELECT SUM(revenue) FROM sales_daily WHERE date BETWEEN ? AND ?",
        (date_from, max_date)
    ).fetchone()[0] or 0

    # Прибыль ~8.8% от выручки (по последним данным)
    profit_30 = revenue_30 * 0.088
    tax_reserve = profit_30 * TAX_RATE

    print(f"  Резерв налога УСН 15%:  {money(tax_reserve)}  (от прибыли за 30д)")

    # Итого денег в разных местах
    total_money = on_account + owed_by_ozon + frozen + in_transit
    print(f"\n  ВСЕГО ДЕНЕГ:            {money(total_money)}")
    print(f"    На счету:             {on_account:>12,.0f} ₽  ({on_account/total_money*100 if total_money else 0:.1f}%)")
    print(f"    У Ozon:               {owed_by_ozon:>12,.0f} ₽  ({owed_by_ozon/total_money*100 if total_money else 0:.1f}%)")
    print(f"    В товаре:             {frozen:>12,.0f} ₽  ({frozen/total_money*100 if total_money else 0:.1f}%)")

    # === 2. ЧТО ЗАБРАТЬ ===
    print("\n[2] ЧТО ЗАБРАТЬ")

    # Резервы
    reserve_tax = tax_reserve

    # Резерв закупок = план из procurement_plan (только будущие платежи)
    today = datetime.now()
    plan_proc = con.execute("""
        SELECT SUM(amount) FROM procurement_plan
        WHERE status = 'planned' AND due_date >= ?
    """, (today.strftime("%Y-%m-%d"),)).fetchone()[0] or 0

    # Резерв штрафов = 3% от выручки
    reserve_fines = revenue_30 * 0.03

    # Свободно = на счету + у Ozon − налог − план закупок − штрафы
    free_money = on_account + owed_by_ozon - reserve_tax - plan_proc - reserve_fines

    print(f"  На счету + у Ozon:      {money(on_account + owed_by_ozon)}")
    print(f"  − Резерв налога:        {money(-reserve_tax)}")
    if plan_proc > 0:
        print(f"  − План закупок:         {money(-plan_proc)}")
    else:
        print(f"  − План закупок:         0 ₽  (нет плана)")
    print(f"  − Резерв штрафов (3%):  {money(-reserve_fines)}")
    print(f"  ─────────────────────────────────")
    print(f"  МОЖНО ЗАБРАТЬ:          {money(max(0, free_money))}")

    if free_money > 50000:
        print(f"  ✅ Свободно {free_money:,.0f} ₽ — можно забрать")
    elif free_money > 10000:
        print(f"  ⚠️ Свободно {free_money:,.0f} ₽ — забирать осторожно")
    else:
        print(f"  ❌ Свободных денег мало ({free_money:,.0f} ₽)")

    # Пояснение
    print(f"\n  ПОЯСНЕНИЕ:")
    print(f"    На счету: {money(on_account)}")
    print(f"    У Ozon:   {money(owed_by_ozon)}  (точно из API)")
    print(f"    В товаре: {money(frozen)}  (уже закуплено, не резерв)")
    print(f"    Налог:    {money(reserve_tax)}  (реальный отложенный расход)")

    # === 3. ПРОГНОЗ 14 ДНЕЙ ===
    print("\n[3] ПРОГНОЗ 14 ДНЕЙ (приходы/расходы)")

    # Приходы: когда Ozon выплатит (по факту — раз в неделю, обычно)
    # Пока нет данных — упростим
    today = datetime.now()
    print(f"  Приходы от Ozon:         нет данных о датах выплат")
    print(f"  Платежи поставщикам:     нет плана закупок")

    # === 4. ОБОРОТ ДЕНЕГ ===
    print("\n[4] ОБОРОТ ДЕНЕГ")

    # Что вложили за 30 дней: себестоимость проданного
    cogs_30 = 0
    rows = con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
        GROUP BY p.sku
    """, (date_from, max_date)).fetchall()
    for r in rows:
        cogs_30 += (r["cost_price"] or 0) * (r["orders"] or 0)

    # Получили за 30 дней: прибыль
    if cogs_30 > 0:
        turnover = revenue_30 / cogs_30  # сколько раз обернулся 1 рубль
        days_per_turn = 30 / turnover if turnover > 0 else 0
        print(f"  За 30 дней:")
        print(f"    Вложили в закупку:   {money(cogs_30)}")
        print(f"    Получили выручки:    {money(revenue_30)}")
        print(f"    Оборот:              {turnover:.2f}x  (во сколько раз прокрутился рубль)")
        print(f"    Дней на оборот:      {days_per_turn:.1f}")
    else:
        print(f"  Нет данных о себестоимости проданного")

    con.close()
    print()
    print("=" * 80)
    print("ЧТО ЗАПОЛНИТЬ ВРУЧНУЮ (лист ВВОД):")
    print("  1. На счету сейчас (₽)")
    print("  2. План закупок (кому/сколько/когда)")
    print("  3. Даты выплат Ozon (если знаете)")
    print("=" * 80)


if __name__ == "__main__":
    main()
