"""
daily_dashboard.py — пульт управления магазином Ozon.
4 блока: СЕГОДНЯ / ДЕЛАЙ / ДЕНЬГИ / РЕЗУЛЬТАТ.
План действий берётся из plan_core.
"""
import sqlite3
import os
from datetime import datetime, timedelta

from plan_core import get_actions

DB = "ozon.db"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
PREMIUM_FIXED  = 4990.0
TAX_PCT        = 0.15


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def line(char="=", n=118):
    print(char * n)


def money(x):
    return f"{x:>13,.0f} ₽"


def pct(x):
    return f"{x*100:>6.1f}%"


def ensure_snapshots_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            run_at TEXT PRIMARY KEY,
            period_from TEXT,
            period_to TEXT,
            revenue REAL,
            profit REAL,
            margin REAL,
            orders INTEGER,
            avg_check REAL
        )
    """)
    con.commit()


def block_today(con):
    line()
    print("СЕГОДНЯ")
    line()

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if not max_date:
        print("  Нет данных в sales_daily.")
        return

    print(f"  Последняя дата в базе: {max_date}")
    print(f"  (сегодня по системе:    {today})\n")

    age = (datetime.now() - datetime.strptime(max_date, "%Y-%m-%d")).days
    if age >= 2:
        print(f"  [ВНИМАНИЕ] Данные отстают на {age} дня. Пора обновить .xlsx в downloads/.")
        print()

    row = con.execute("""
        SELECT SUM(revenue), SUM(orders_units),
               SUM(CASE WHEN orders_units > 0 THEN 1 ELSE 0 END)
        FROM sales_daily WHERE date = ?
    """, (max_date,)).fetchone()
    rev_d, ord_d, sku_d = row[0] or 0, row[1] or 0, row[2] or 0

    row7 = con.execute("""
        SELECT AVG(rev), AVG(ord) FROM (
            SELECT date, SUM(revenue) AS rev, SUM(orders_units) AS ord
            FROM sales_daily WHERE date BETWEEN ? AND ?
            GROUP BY date
        )
    """, (week_ago, max_date)).fetchone()
    rev_avg = row7[0] or 0
    ord_avg = row7[1] or 0

    print(f"  {'Показатель':<20} {'Вчера':>14} {'Среднее 7д':>14} {'Δ':>10}")
    print("  " + "-" * 60)
    print(f"  {'Выручка':<20} {money(rev_d)} {money(rev_avg)} {(rev_d - rev_avg):>+10,.0f}")
    print(f"  {'Заказы':<20} {ord_d:>14} {ord_avg:>14.1f} {(ord_d - ord_avg):>+10.1f}")
    print(f"  {'Активных SKU':<20} {sku_d:>14}")

    top = con.execute("""
        SELECT p.offer_id, p.name, sd.revenue, sd.orders_units
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date = ? AND sd.revenue > 0
          AND p.is_archived = 0
        ORDER BY sd.revenue DESC LIMIT 3
    """, (max_date,)).fetchall()
    if top:
        print("\n  Топ-3 вчера:")
        for offer_id, name, rev, orders in top:
            print(f"    {offer_id:<18} {name[:40]:<40} {money(rev)} ({orders} зак.)")
    print()


def block_actions(con):
    line()
    print("ДЕЛАЙ")
    line()

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    actions = get_actions(con, month_ago, max_date)

    if not actions:
        print("\n  Действий нет.")
        print()
        return

    total_effect = sum(a["effect"] for a in actions)

    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    print(f"\n  Всего SKU к работе: {len(actions)}, потенциал: {total_effect:,.0f} ₽/мес")
    print(f"  {'Категория':<12} {'SKU':>4} {'Эффект':>12}")
    print("  " + "-" * 32)
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp = cats[cat]
            grp_effect = sum(g["effect"] for g in grp)
            print(f"  {cat:<12} {len(grp):>4} {grp_effect:>11,.0f} ₽")

    print(f"\n  ТОП-10 действий:")
    print(f"  {'#':<4} {'Категория':<12} {'Offer ID':<18} {'Что':<32} {'Эффект':>10}")
    print("  " + "-" * 84)
    for i, a in enumerate(actions[:10], 1):
        name = (a["name"] or "")[:31]
        print(f"  {i:<4} {a['category']:<12} {a['offer_id']:<18} {name:<32} "
              f"{a['effect']:>9,.0f} ₽")
    print()


def block_money(con):
    line()
    print("ДЕНЬГИ")
    line()

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if not max_date:
        print("  Нет данных.")
        return

    periods = [
        ("7 дней",  (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), max_date),
        ("30 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"), max_date),
        ("с 1 августа", "2026-08-01", max_date),
    ]

    print(f"\n  {'Период':<14} {'Выручка':>13} {'Себест':>13} {'Комис':>10} "
          f"{'Услуги':>10} {'Прибыль':>11} {'Маржа':>7} {'Зак':>5} {'Ср.чек':>10}")
    print("  " + "-" * 110)

    for label, d1, d2 in periods:
        rows = con.execute("""
            SELECT p.sku, p.cost_price,
                   SUM(sd.revenue) AS revenue,
                   SUM(sd.orders_units) AS orders
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
        """, (d1, d2)).fetchall()

        rev = cost = comm = serv = profit = 0.0
        orders = 0
        for sku, cost_price, r, o in rows:
            r = r or 0
            o = o or 0
            cost_price = cost_price or 0
            c = cost_price * o
            cm = r * COMMISSION_PCT
            sv = r * SERVICES_PCT
            pb = r - c - cm - sv
            tx = pb * TAX_PCT if pb > 0 else 0
            rev += r; cost += c; comm += cm; serv += sv
            profit += pb - tx
            orders += o
        margin = profit / rev if rev else 0
        avg = rev / orders if orders else 0

        print(f"  {label:<14} {money(rev)} {money(cost)} "
              f"{comm:>9,.0f}₽ {serv:>9,.0f}₽ {profit:>10,.0f}₽ "
              f"{pct(margin)} {orders:>5} {avg:>9,.0f}₽")

    print(f"\n  Постоянные расходы:")
    print(f"    PremiumSubscription (фикс):   {PREMIUM_FIXED:>10,.0f} ₽/мес")
    print(f"    (в расчёте маржи выше НЕ учтён — относится ко всему магазину)")
    print()


def block_result(con):
    line()
    print("РЕЗУЛЬТАТ")
    line()

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = "2026-08-01"  # реальный старт бизнеса

    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = comm = serv = profit = 0.0
    orders = 0
    for sku, cost_price, r, o in rows:
        r = r or 0; o = o or 0; cost_price = cost_price or 0
        c = cost_price * o
        cm = r * COMMISSION_PCT
        sv = r * SERVICES_PCT
        pb = r - c - cm - sv
        tx = pb * TAX_PCT if pb > 0 else 0
        rev += r; cost += c; comm += cm; serv += sv
        profit += pb - tx; orders += o
    margin = profit / rev if rev else 0
    avg = rev / orders if orders else 0

    ensure_snapshots_table(con)
    prev = con.execute("""
        SELECT run_at, period_from, period_to, revenue, profit, margin, orders, avg_check
        FROM dashboard_snapshots
        ORDER BY run_at DESC LIMIT 1
    """).fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT OR REPLACE INTO dashboard_snapshots
        (run_at, period_from, period_to, revenue, profit, margin, orders, avg_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, min_date, max_date, rev, profit, margin, orders, avg))
    con.commit()

    if prev:
        p_run, p_from, p_to, p_rev, p_profit, p_margin, p_orders, p_avg = prev
        print(f"\n  Предыдущий запуск: {p_run}")
        print(f"  Период: {p_from} — {p_to}\n")

        def delta(curr, old):
            if old == 0:
                return "—"
            d = (curr - old) / abs(old) * 100
            return f"{d:+.1f}%"

        print(f"  {'Показатель':<18} {'Сейчас':>14} {'Прошлый раз':>14} {'Δ':>10}")
        print("  " + "-" * 60)
        print(f"  {'Выручка':<18} {money(rev)} {money(p_rev)} {delta(rev, p_rev):>10}")
        print(f"  {'Прибыль':<18} {money(profit)} {money(p_profit)} {delta(profit, p_profit):>10}")
        print(f"  {'Маржа':<18} {pct(margin)} {pct(p_margin)} {delta(margin, p_margin):>10}")
        print(f"  {'Заказы':<18} {orders:>14} {p_orders:>14} {delta(orders, p_orders):>10}")
        print(f"  {'Ср. чек':<18} {money(avg)} {money(p_avg)} {delta(avg, p_avg):>10}")
    else:
        print("\n  Первый запуск. Снапшот сохранён.")
        print(f"  Выручка:  {money(rev)}")
        print(f"  Прибыль:  {money(profit)}")
        print(f"  Маржа:    {pct(margin)}")
        print(f"  Заказов:  {orders}")
        print(f"  Ср. чек:  {money(avg)}")
    print()


def main():
    clear()
    con = sqlite3.connect(DB)

    print()
    line("█")
    print(f"  ПУЛЬТ УПРАВЛЕНИЯ OZON   |   {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"  Ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}% (реальные из accruals)")
    line("█")
    print()

    block_today(con)
    block_actions(con)
    block_money(con)
    block_result(con)

    print("=" * 118)
    print("  Готово. План действий — из plan_core.py, детали: py action_plan.py")
    print("=" * 118)

    con.close()


if __name__ == "__main__":
    main()
