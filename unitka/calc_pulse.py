"""unitka/calc_pulse.py — управленческий экран ПУЛЬТ (финальная версия)."""
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, date
import calendar

from .db import connect
from . import report_layout as rl
from .calc_taxes import build as build_taxes
from .finance_core import receivables as calc_receivables, inventory_value, tax_rate_pct
from . import calc_funnel

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "ПУЛЬТ"


def get_manual_inputs(sh):
    cash = 0.0
    try:
        ws = sh.worksheet("Ручной ввод")
        vals = ws.get_all_values()
        for row in vals:
            if len(row) < 2:
                continue
            key = row[0].strip().lower()
            val_str = row[1].replace(" ", "").replace(",", ".").strip()
            if not val_str or val_str == "значение":
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue
            if "деньги" in key or "счет" in key:
                cash = val
    except Exception:
        pass
    return cash


def _load_position_trends():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT sku,
               AVG(CASE WHEN date >= date('now', '-7 days') THEN position END) AS pos_now,
               AVG(CASE WHEN date < date('now', '-7 days') AND date >= date('now', '-14 days') THEN position END) AS pos_prev
        FROM analytics_manual
        WHERE position IS NOT NULL AND position > 0
        GROUP BY sku
    """)
    rows = cur.fetchall()
    conn.close()
    trends = {}
    for r in rows:
        sku = str(r[0])
        pos_now = r[1]
        pos_prev = r[2]
        if pos_now and pos_prev and pos_now > pos_prev + 20:
            trends[sku] = {
                "pos_now": round(pos_now, 1),
                "pos_prev": round(pos_prev, 1),
                "drop": round(pos_now - pos_prev, 1),
            }
    return trends


def _load_content_ratings():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT sku, content_rating FROM sku_content_rating")
        data = {str(r[0]): r[1] for r in cur.fetchall()}
    except Exception:
        data = {}
    conn.close()
    return data


def _load_purchase_recommendations():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sku, forecast_qty, forecast_revenue
            FROM forecast WHERE forecast_qty > 0
            ORDER BY forecast_qty DESC LIMIT 5
        """)
        data = [{"sku": r[0], "qty": r[1], "revenue": r[2]} for r in cur.fetchall()]
    except Exception:
        data = []
    conn.close()
    return data


def _load_strategies(sh):
    """Возвращает список стратегий с прогрессом."""
    try:
        ws = sh.worksheet("Стратегии")
        rows = ws.get_all_values()
    except Exception:
        return []
    result = []
    for row in rows:
        if len(row) < 7:
            continue
        name = row[0].strip()
        if not name or "СТРАТЕГИЧЕСКИЕ" in name or "Стратегия" == name:
            continue
        result.append({
            "name": name,
            "metric": row[1].strip(),
            "target": row[2].strip(),
            "current": row[3].strip(),
            "progress": row[4].strip(),
            "deadline": row[5].strip() if len(row) > 5 else "",
            "status": row[6].strip() if len(row) > 6 else "",
        })
    return result


def _load_kpi_deviations(sh):
    """Возвращает топ-3 отклонения от плана."""
    try:
        ws = sh.worksheet("KPI")
        rows = ws.get_all_values()
    except Exception:
        return []
    result = []
    for row in rows:
        if len(row) < 7:
            continue
        name = row[0].strip()
        if not name or "KPI" == name or "Метрика" in name:
            continue
        status = row[6].strip() if len(row) > 6 else ""
        if "🔴" in status or "🟡" in status:
            try:
                delta_pct = row[5].strip()
            except Exception:
                delta_pct = "—"
            result.append({
                "name": name,
                "plan": row[1].strip(),
                "fact": row[2].strip(),
                "forecast": row[3].strip(),
                "delta": delta_pct,
                "status": status,
            })
    # Сортируем: сначала красные, потом жёлтые
    result.sort(key=lambda x: (0 if "🔴" in x["status"] else 1))
    return result[:3]


def _next_tax_payment():
    """Возвращает ближайший налоговый платёж и дней до него."""
    today = date.today()
    payments = [
        ("28.04", date(today.year, 4, 28), "Аванс УСН за 1 квартал"),
        ("28.07", date(today.year, 7, 28), "Аванс УСН за полугодие"),
        ("28.10", date(today.year, 10, 28), "Аванс УСН за 9 месяцев"),
        ("28.04", date(today.year + 1, 4, 28), "Итоговый налог за год"),
        ("28.12", date(today.year, 12, 28), "Фиксированные взносы ИП 57 390"),
        ("01.07", date(today.year + 1, 7, 1), "1% взносов с превышения 300к (если база Д−Р > 300к)"),
    ]
    upcoming = []
    for label, dt, name in payments:
        if dt >= today:
            days = (dt - today).days
            upcoming.append((days, dt.strftime("%d.%m.%Y"), name))
    upcoming.sort()
    if upcoming:
        days, dt_str, name = upcoming[0]
        return f"{name}: до {dt_str} ({days} дн.)"
    return "—"


def _revenue_compare(d_from, d_to):
    """Сравнивает выручку за период с аналогичным периодом прошлого месяца."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals
        WHERE date >= ? AND date < ?
    """, (d_from, d_to))
    current = cur.fetchone()[0] or 0

    # Аналогичный период прошлого месяца
    from_dt = datetime.strptime(d_from, "%Y-%m-%d")
    to_dt = datetime.strptime(d_to, "%Y-%m-%d")
    days = (to_dt - from_dt).days
    prev_to = from_dt
    prev_from = prev_to - timedelta(days=days)
    cur.execute("""
        SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals
        WHERE date >= ? AND date < ?
    """, (prev_from.strftime("%Y-%m-%d"), prev_to.strftime("%Y-%m-%d")))
    previous = cur.fetchone()[0] or 0
    conn.close()

    if previous == 0:
        delta_text = "нет данных за прошлый месяц"
    else:
        delta_pct = (current - previous) / previous * 100
        arrow = "⬆" if delta_pct > 0 else "⬇"
        delta_text = f"{arrow} {abs(delta_pct):.0f}% (было {previous:,.0f} ₽)"
    return current, delta_text


def build(sh):
    conn = connect()
    cur = conn.cursor()

    # --- 1. АССОРТИМЕНТ ---
    cur.execute("SELECT MAX(period) FROM abc_xyz")
    period = cur.fetchone()[0]
    data = {"A": {"X": 0, "Y": 0, "Z": 0, "N/A": 0}, "B": {"X": 0, "Y": 0, "Z": 0, "N/A": 0}, "C": {"X": 0, "Y": 0, "Z": 0, "N/A": 0}}
    profits = {"A": 0.0, "B": 0.0, "C": 0.0}
    capitals = {"A": 0.0, "B": 0.0, "C": 0.0}
    if period:
        cur.execute("""
            SELECT abc_class, xyz_class, COUNT(*) as cnt, SUM(profit) as profit, SUM(capital) as capital
            FROM abc_xyz WHERE period = ? GROUP BY abc_class, xyz_class
        """, (period,))
        for r in cur.fetchall():
            abc = r["abc_class"]; xyz = r["xyz_class"]
            if abc in data and xyz in data[abc]:
                data[abc][xyz] = r["cnt"]
                profits[abc] += (r["profit"] or 0)
                capitals[abc] += (r["capital"] or 0)
    total_profit = sum(profits.values())
    total_capital = sum(capitals.values())
    low_hist = episodic = 0
    if period:
        cur.execute("SELECT COUNT(*) FROM abc_xyz WHERE period = ? AND xyz_class = 'N/A' AND active_months < 3", (period,))
        low_hist = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM abc_xyz WHERE period = ? AND xyz_class = 'N/A' AND active_months >= 3", (period,))
        episodic = cur.fetchone()[0]

    # --- 2. УБЫТОЧНЫЕ SKU ---
    active_skus = set()
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if last_date:
        cur.execute("SELECT sku FROM stock_daily WHERE date = ? AND (fbo_present + fbs_present) > 0", (last_date,))
        for r in cur.fetchall(): active_skus.add(str(r[0]))
    cur.execute("SELECT DISTINCT sku FROM realization_daily WHERE date >= date('now', '-30 days') AND is_return = 0")
    for r in cur.fetchall(): active_skus.add(str(r[0]))

    cur.execute("""
        SELECT r.sku, SUM(r.sale_price + r.bonus + r.coinvestment) AS revenue,
               SUM(CASE WHEN r.is_return = 0 THEN r.quantity * c.cost_price ELSE 0 END) AS cogs,
               SUM(ABS(s.amount)) AS ozon_exp
        FROM realization_daily r
        LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON r.sku = c.sku
        LEFT JOIN accrual_sku_daily s ON r.sku = s.sku AND r.date = s.date
        WHERE r.date LIKE '2026-%' GROUP BY r.sku
    """)
    loss_skus_count = 0
    total_loss = 0.0
    for sku, rev, cogs, exp in cur.fetchall():
        if str(sku) in active_skus:
            p = rev - cogs - exp
            if p < 0:
                loss_skus_count += 1
                total_loss += abs(p)

    # --- 3. НЕЛИКВИД ---
    non_liquid = 0.0
    if last_date:
        cur.execute("""
            SELECT SUM((s.fbo_present + s.fbs_present) * c.cost_price)
            FROM stock_daily s
            LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history WHERE date_from <= ? GROUP BY sku)) c ON s.sku = c.sku
            WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
            AND s.sku NOT IN (SELECT sku FROM realization_daily WHERE date >= date(?, '-60 days') AND is_return = 0)
        """, (last_date, last_date, last_date))
        non_liquid = cur.fetchone()[0] or 0.0

    # --- 4. ДЕБИТОРКА ---
    receivables = calc_receivables(cur)       # фактический баланс Ozon
    stock_capital = inventory_value(cur)      # весь товар на складах × себестоимость (как в Балансе)
    conn.close()

    tax_data = build_taxes(2026, tax_rate_pct(sh))
    total_burden = tax_data["tax_to_pay"] + tax_data["total_contrib"]
    cash = get_manual_inputs(sh)
    cash_gap = 0.0
    if cash < total_burden:
        cash_gap = total_burden - cash - receivables
        if cash_gap < 0: cash_gap = 0.0
    next_payment = _next_tax_payment()

    # --- 5. ВОРОНКА ---
    dfrom = (datetime.now().date() - timedelta(days=30)).isoformat()
    dto = datetime.now().date().isoformat()
    try:
        funnel_items = calc_funnel._load_period(dfrom, dto, only_in_stock=False)
    except Exception:
        funnel_items = []
    ratings = _load_content_ratings()
    trends = _load_position_trends()
    offer_map = {i["sku"]: i["offer_id"] for i in funnel_items}

    plan_by_sku = {}
    if funnel_items:
        for i in funnel_items:
            if i["impressions"] < 100 and i["qty"] > 0:
                sku = i["sku"]
                if sku not in plan_by_sku:
                    plan_by_sku[sku] = {"offer": i["offer_id"] or sku, "problems": [], "cost": 0}
                plan_by_sku[sku]["problems"].append(f"мало показов ({i['impressions']})")
                plan_by_sku[sku]["cost"] += (100 - i["impressions"])
        for i in funnel_items:
            if i["impressions"] >= 500 and i["orders"] == 0 and i["qty"] > 0:
                sku = i["sku"]
                if sku not in plan_by_sku:
                    plan_by_sku[sku] = {"offer": i["offer_id"] or sku, "problems": [], "cost": 0}
                reason = f"{i['impressions']} показов, 0 заказов"
                extras = []
                if i.get("position") and i["position"] > 100: extras.append(f"позиция {i['position']:.0f}")
                if i.get("avg_price") and i["avg_price"] > 0: extras.append(f"цена {i['avg_price']:,.0f} ₽")
                if sku in ratings and ratings[sku] is not None and ratings[sku] < 0.6:
                    extras.append(f"контент-рейтинг {ratings[sku]:.2f}")
                if extras: reason += " (" + "; ".join(extras) + ")"
                plan_by_sku[sku]["problems"].append(reason)
                plan_by_sku[sku]["cost"] += i["impressions"] * 100
        for i in funnel_items:
            if i.get("drr") and i["drr"] > 30:
                sku = i["sku"]
                if sku not in plan_by_sku:
                    plan_by_sku[sku] = {"offer": i["offer_id"] or sku, "problems": [], "cost": 0}
                plan_by_sku[sku]["problems"].append(f"ДРР {i['drr']}% — реклама убыточна")
                plan_by_sku[sku]["cost"] += i["drr"] * 1000
        for sku, t in trends.items():
            offer = offer_map.get(sku) or sku
            if sku not in plan_by_sku:
                plan_by_sku[sku] = {"offer": offer, "problems": [], "cost": 0}
            plan_by_sku[sku]["problems"].append(f"позиция упала с {t['pos_prev']} на {t['pos_now']}")
            plan_by_sku[sku]["cost"] += t["drop"] * 100
        for i in funnel_items:
            if i["qty"] == 0 and i["orders"] > 0:
                sku = i["sku"]
                if sku not in plan_by_sku:
                    plan_by_sku[sku] = {"offer": i["offer_id"] or sku, "problems": [], "cost": 0}
                plan_by_sku[sku]["problems"].append(f"продаётся ({i['orders']} заказов), но остаток 0")
                plan_by_sku[sku]["cost"] += i["orders"] * 1000
        for i in funnel_items:
            if i.get("position") and i["position"] > 100 and i["impressions"] >= 100:
                sku = i["sku"]
                if sku not in plan_by_sku:
                    plan_by_sku[sku] = {"offer": i["offer_id"] or sku, "problems": [], "cost": 0}
                if not any("позиция" in p for p in plan_by_sku[sku]["problems"]):
                    plan_by_sku[sku]["problems"].append(f"позиция {i['position']:.0f} (низкая видимость)")
                    plan_by_sku[sku]["cost"] += i["impressions"] * 20
    funnel_plan = []
    for sku, p in plan_by_sku.items():
        funnel_plan.append({"cost": p["cost"], "text": f"🔴 {p['offer']}: " + "; ".join(p["problems"])})
    funnel_plan.sort(key=lambda x: x["cost"], reverse=True)

    # --- 6. ФИНАНСОВЫЕ ПРОБЛЕМЫ ---
    actions = []
    if total_loss > 0:
        actions.append({"cost": total_loss, "text": f"🔴 Убыточные SKU ({loss_skus_count} шт): Теряете {total_loss:,.0f} ₽. Поднять цены или снять с продажи."})
    if cash_gap > 0:
        actions.append({"cost": cash_gap, "text": f"🔴 Кассовый разрыв: Не хватает {cash_gap:,.0f} ₽. Ближайший платёж: {next_payment}"})
    if non_liquid > 0:
        actions.append({"cost": non_liquid, "text": f"🟡 Неликвид (>60 дней): Заморожено {non_liquid:,.0f} ₽. Запустить распродажу."})
    actions.sort(key=lambda x: x["cost"], reverse=True)

    # --- 7. Сравнение с прошлым месяцем ---
    today_d = date.today()
    month_start = today_d.replace(day=1).strftime("%Y-%m-%d")
    today_str = today_d.strftime("%Y-%m-%d")
    rev_current, rev_delta = _revenue_compare(month_start, today_str)

    # --- 8. СВОДКА ВОРОНКИ ---
    total_imp = sum(i["impressions"] for i in funnel_items)
    total_ord = sum(i["orders"] for i in funnel_items)
    total_views = sum(i["views"] for i in funnel_items)
    total_cart = sum(i["cart"] for i in funnel_items)
    conv_total = round(total_ord / total_imp * 100, 2) if total_imp else 0
    c_cart = round(total_cart / total_views * 100, 2) if total_views else 0

    return {
        "period": period, "data": data, "profits": profits, "capitals": capitals,
        "total_profit": total_profit, "total_capital": total_capital, "stock_capital": stock_capital,
        "low_hist": low_hist, "episodic": episodic,
        "actions": actions, "funnel_plan": funnel_plan,
        "funnel_total_imp": total_imp, "funnel_total_ord": total_ord,
        "funnel_conv": conv_total, "funnel_c_cart": c_cart,
        "purchases": _load_purchase_recommendations(),
        "strategies": _load_strategies(sh),
        "kpi_deviations": _load_kpi_deviations(sh),
        "next_payment": next_payment,
        "rev_current": rev_current, "rev_delta": rev_delta,
    }


def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    res = build(sh)
    if not res:
        print("Нет данных")
        return

    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=150, cols=5)

    values = []
    values.append([f"ПУЛЬТ — {datetime.now().strftime('%Y-%m-%d %H:%M')}", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 1. Финансы
    values.append(["ЧТО ДЕЛАТЬ СЕГОДНЯ (деньги)", "", "", "", ""])
    if res["actions"]:
        for act in res["actions"]:
            values.append([act["text"], "", "", "", ""])
    else:
        values.append(["🟢 Критичных финансовых проблем не обнаружено.", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 2. Стратегические цели
    values.append(["СТРАТЕГИЧЕСКИЕ ЦЕЛИ", "", "", "", ""])
    if res["strategies"]:
        for s in res["strategies"]:
            line = f"{s['status']} {s['name']}: {s['current']} → {s['target']} (прогресс {s['progress']})"
            values.append([line, "", "", "", ""])
    else:
        values.append(["Нет стратегий — заполните лист «Стратегии»", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 3. KPI (отклонения)
    values.append(["KPI — ОТКЛОНЕНИЯ ОТ ПЛАНА", "", "", "", ""])
    if res["kpi_deviations"]:
        for k in res["kpi_deviations"]:
            line = f"{k['status']} {k['name']}: план {k['plan']} / факт {k['fact']} ({k['delta']})"
            values.append([line, "", "", "", ""])
    else:
        values.append(["Все KPI в норме", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 4. План работы по воронке
    values.append(["ПЛАН РАБОТЫ ПО ВОРОНКЕ (топ-10)", "", "", "", ""])
    if res["funnel_plan"]:
        for p in res["funnel_plan"][:10]:
            values.append([p["text"], "", "", "", ""])
    else:
        values.append(["🟢 Проблем в воронке не обнаружено.", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 5. Закупки
    values.append(["ЗАКУПКИ (топ-5)", "", "", "", ""])
    if res["purchases"]:
        for p in res["purchases"]:
            values.append([f"🟡 {p['sku']}: закупить {p['qty']:.0f} шт (прогноз выручки {p['revenue']:,.0f} ₽)", "", "", "", ""])
    else:
        values.append(["Нет рекомендаций по закупкам", "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 6. Ассортимент
    values.append(["АССОРТИМЕНТ", "", "", "", ""])
    total_sku = sum(sum(d.values()) for d in res["data"].values())
    a_share = int((res["profits"]["A"] / res["total_profit"] * 100)) if res["total_profit"] > 0 else 0
    b_share = int((res["profits"]["B"] / res["total_profit"] * 100)) if res["total_profit"] > 0 else 0
    c_share = int((res["profits"]["C"] / res["total_profit"] * 100)) if res["total_profit"] > 0 else 0
    for line in [
        f"Всего SKU: {total_sku}",
        f"A: {sum(res['data']['A'].values())} SKU = {a_share}% прибыли",
        f"B: {sum(res['data']['B'].values())} SKU = {b_share}% прибыли",
        f"C: {sum(res['data']['C'].values())} SKU = {c_share}% прибыли",
        f"Мало истории: {res['low_hist']}",
        f"Эпизодический: {res['episodic']}",
        f"Капитал в товаре: {res['stock_capital']:,.0f} ₽ (в т.ч. по продающимся SKU: {res['total_capital']:,.0f} ₽)",
    ]:
        values.append([line, "", "", "", ""])
    values.append(["", "", "", "", ""])

    # 7. Воронка
    values.append(["ВОРОНКА (30 дней)", "", "", "", ""])
    for line in [
        f"Показы: {res['funnel_total_imp']:,}",
        f"Заказы: {res['funnel_total_ord']:,}",
        f"Конверсия показ→заказ: {res['funnel_conv']}%",
        f"Конверсия в корзину: {res['funnel_c_cart']}%",
        f"Выручка (текущий месяц): {res['rev_current']:,.0f} ₽ — {res['rev_delta']}",
    ]:
        values.append([line, "", "", "", ""])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")

    print(f"ПУЛЬТ обновлен.")
    print(f"  Финансовых проблем: {len(res['actions'])}")
    print(f"  Стратегий: {len(res['strategies'])}")
    print(f"  KPI-отклонений: {len(res['kpi_deviations'])}")
    print(f"  Проблем воронки: {len(res['funnel_plan'])}")
    print(f"  Закупок: {len(res['purchases'])}")
    print(f"  Ближайший платёж: {res['next_payment']}")
    print(f"  Выручка: {res['rev_current']:,.0f} ₽ — {res['rev_delta']}")


if __name__ == "__main__":
    main()
