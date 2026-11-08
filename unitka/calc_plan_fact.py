"""unitka/calc_plan_fact.py — план/факт и KPI (с разделением на активные и распродажу)."""
import os
import logging
from datetime import datetime, date, timedelta
import calendar

import gspread
from google.oauth2.service_account import Credentials

from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

PLAN_SHEET = "План"
KPI_SHEET = "KPI"
LIQUIDATION_DAYS = 60  # SKU без продаж N дней считаем неликвидом


# KPI: (ключ, название, единица, направление)
KPI_LIST = [
    ("revenue_total", "Выручка (всего)", "₽", "up"),
    ("revenue_active", "Выручка (активные SKU)", "₽", "up"),
    ("revenue_liq", "Выручка (распродажа)", "₽", "up"),
    ("profit_total", "Прибыль (всего)", "₽", "up"),
    ("profit_active", "Прибыль (активные)", "₽", "up"),
    ("margin_total", "Маржинальность (всего)", "%", "up"),
    ("margin_active", "Маржинальность (активные)", "%", "up"),
    ("orders_total", "Заказы (всего)", "шт", "up"),
    ("drr", "ДРР", "%", "down"),
    ("conversion", "Конверсия показ→заказ", "%", "up"),
    ("aov", "Средний чек (AOV)", "₽", "up"),
    ("buyout", "Выкупаемость", "%", "up"),
    ("ccc", "CCC (дней)", "дн", "down"),
    ("liq_share_stock", "Доля неликвида в товаре", "%", "down"),
    ("active_share_revenue", "Доля активных в выручке", "%", "up"),
    ("liq_sold_skus", "Распродано SKU за месяц", "шт", "up"),
]


def read_plan(sh):
    """Читает лист «План». Возвращает {month: {type: {kpi_key: value}}}."""
    try:
        ws = sh.worksheet(PLAN_SHEET)
    except gspread.WorksheetNotFound:
        logger.warning("Лист «План» не найден. Создайте его.")
        return {}

    rows = ws.get_all_values()
    if len(rows) < 2:
        return {}

    headers = [h.strip().lower() for h in rows[0]]
    if "месяц" not in headers:
        logger.error("В листе «План» нет колонки «Месяц»")
        return {}
    month_col = headers.index("месяц")
    type_col = headers.index("тип") if "тип" in headers else None

    # Маппинг колонок к KPI
    col_map = {}
    for key, name, _, _ in KPI_LIST:
        for i, h in enumerate(headers):
            if name.lower() in h or h in name.lower():
                col_map[key] = i
                break

    result = {}
    for row in rows[1:]:
        if len(row) <= month_col:
            continue
        month = row[month_col].strip()
        if not month or not (len(month) == 7 and month[4] == "-"):
            continue
        type_name = row[type_col].strip() if type_col is not None and type_col < len(row) else "ИТОГО"
        if month not in result:
            result[month] = {}
        result[month][type_name] = {}
        for key, col_idx in col_map.items():
            if col_idx >= len(row):
                continue
            val = row[col_idx].replace(" ", "").replace(",", ".").replace("%", "").strip()
            if val:
                try:
                    result[month][type_name][key] = float(val)
                except ValueError:
                    pass
    return result


def _is_liquid_sku(cur, sku, d_from):
    """Проверяет, продавался ли SKU за LIQUIDATION_DAYS до d_from."""
    check_date = (datetime.strptime(d_from, "%Y-%m-%d") - timedelta(days=LIQUIDATION_DAYS)).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT COUNT(*) FROM realization_daily
        WHERE sku = ? AND is_return = 0 AND date >= ? AND date < ?
    """, (sku, check_date, d_from))
    return cur.fetchone()[0] > 0


def calc_fact(month_str):
    y, m = month_str.split("-")
    y, m = int(y), int(m)
    import calendar
    days_in_month = calendar.monthrange(y, m)[1]
    today = date.today()
    if today.year == y and today.month == m:
        days_passed = today.day
    elif (today.year, today.month) > (y, m):
        days_passed = days_in_month
    else:
        days_passed = 0

    d_from = f"{y}-{m:02d}-01"
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d_to = f"{ny}-{nm:02d}-01"

    conn = connect()
    cur = conn.cursor()

    # === Выручка и COGS из accruals (ежедневные начисления) ===
    # Выручка из accruals
    cur.execute("""
        SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) AS rev
        FROM accruals
        WHERE date >= ? AND date < ?
    """, (d_from, d_to))
    revenue_all = cur.fetchone()[0] or 0

    # COGS из realization_daily (только для закрытых месяцев)
    cur.execute("""
        SELECT COALESCE(SUM(r.quantity * c.cost_price), 0) AS cogs
        FROM realization_daily r
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON r.sku = c.sku
        WHERE r.date >= ? AND r.date < ? AND r.is_return = 0
    """, (d_from, d_to))
    cogs_all = cur.fetchone()[0] or 0

    # === Расходы Ozon из finance_transactions (удержания) ===
    cur.execute("""
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions
        WHERE type = 'deduction' AND date >= ? AND date < ?
    """, (d_from, d_to))
    ozon_exp = cur.fetchone()[0] or 0

    profit = revenue_all - cogs_all - ozon_exp

    # === Заказы из postings_daily ===
    cur.execute("""
        SELECT COUNT(DISTINCT posting_number) FROM postings_daily
        WHERE date >= ? AND date < ? AND COALESCE(is_cancelled, 0) = 0
    """, (d_from, d_to))
    orders = cur.fetchone()[0] or 0

    # === Разделение на активные / распродажу ===
    cur.execute("""
        SELECT DISTINCT sku FROM accruals
        WHERE date >= ? AND date < ? AND sale_price > 0
    """, (d_from, d_to))
    month_skus = [str(r[0]) for r in cur.fetchall()]

    active_skus = set()
    liq_skus = set()
    for sku in month_skus:
        if _is_liquid_sku(cur, sku, d_from):
            active_skus.add(sku)
        else:
            liq_skus.add(sku)

    def agg_for(skus_set):
        if not skus_set:
            return {"rev": 0, "cogs": 0, "exp": 0}
        placeholders = ",".join("?" * len(skus_set))
        skus_list = list(skus_set)

        cur.execute(f"""
            SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) AS rev
            FROM accruals
            WHERE date >= ? AND date < ? AND sku IN ({placeholders})
        """, (d_from, d_to, *skus_list))
        rev = cur.fetchone()[0] or 0
        return {"rev": rev, "cogs": 0}

    agg_active = agg_for(active_skus)
    agg_liq = agg_for(liq_skus)

    # Распределяем расходы Ozon пропорционально выручке
    rev_active = agg_active["rev"]
    rev_liq = agg_liq["rev"]
    if revenue_all > 0:
        exp_active = ozon_exp * (rev_active / revenue_all)
        exp_liq = ozon_exp * (rev_liq / revenue_all)
    else:
        exp_active = 0
        exp_liq = 0

    agg_active["exp"] = exp_active
    agg_liq["exp"] = exp_liq
    profit_active_val = agg_active["rev"] - agg_active["cogs"] - agg_active["exp"]

    # === ДРР, конверсия, выкупаемость из analytics_manual ===
    cur.execute("""
        SELECT SUM(orders), SUM(impressions), SUM(buyouts)
        FROM analytics_manual WHERE date >= ? AND date < ?
    """, (d_from, d_to))
    am_orders, am_impressions, am_buyouts = cur.fetchone()
    am_orders = am_orders or 0
    am_impressions = am_impressions or 0
    am_buyouts = am_buyouts or 0

    cur.execute("""
        SELECT AVG(drr) FROM analytics_manual
        WHERE date >= ? AND date < ? AND drr IS NOT NULL AND drr > 0
    """, (d_from, d_to))
    drr = cur.fetchone()[0]

    # === Неликвид в товаре ===
    cur.execute("SELECT MAX(date) FROM stock_daily WHERE date < ?", (d_to,))
    last_stock_date = cur.fetchone()[0]
    liq_stock_value = 0.0
    total_stock_value = 0.0
    if last_stock_date:
        cur.execute("SELECT sku, (fbo_present + fbs_present) FROM stock_daily WHERE date = ?", (last_stock_date,))
        for sku, qty in cur.fetchall():
            if not qty or qty <= 0:
                continue
            sku_str = str(sku)
            cur.execute("""
                SELECT cost_price FROM product_cost_history
                WHERE sku = ? AND date_from <= ? ORDER BY date_from DESC LIMIT 1
            """, (sku_str, last_stock_date))
            cp = cur.fetchone()
            cost = cp[0] if cp and cp[0] else 0
            val = qty * cost
            total_stock_value += val
            if not _is_liquid_sku(cur, sku_str, last_stock_date):
                liq_stock_value += val

    daily_cogs = cogs_all / days_passed if days_passed > 0 else 0
    ccc = (total_stock_value / daily_cogs) if daily_cogs > 0 else 0

    margin = (profit / revenue_all * 100) if revenue_all > 0 else 0
    margin_active = (profit_active_val / agg_active["rev"] * 100) if agg_active["rev"] > 0 else 0
    conversion = (am_orders / am_impressions * 100) if am_impressions > 0 else 0
    buyout = (am_buyouts / am_orders * 100) if am_orders > 0 else 0
    aov = (revenue_all / orders) if orders > 0 else 0
    liq_share_stock = (liq_stock_value / total_stock_value * 100) if total_stock_value > 0 else 0
    active_share_revenue = (agg_active["rev"] / revenue_all * 100) if revenue_all > 0 else 0

    conn.close()

    return {
        "revenue_total": round(revenue_all, 2),
        "revenue_active": round(agg_active["rev"], 2),
        "revenue_liq": round(agg_liq["rev"], 2),
        "profit_total": round(profit, 2),
        "profit_active": round(profit_active_val, 2),
        "margin_total": round(margin, 2),
        "margin_active": round(margin_active, 2),
        "orders_total": orders,
        "drr": round(drr, 2) if drr else 0,
        "conversion": round(conversion, 2),
        "aov": round(aov, 2),
        "buyout": round(buyout, 2),
        "ccc": round(ccc, 1) if ccc else 0,
        "liq_share_stock": round(liq_share_stock, 2),
        "active_share_revenue": round(active_share_revenue, 2),
        "liq_sold_skus": len(liq_skus),
        "days_passed": days_passed,
        "days_in_month": days_in_month,
    }


def forecast_month(fact_value, days_passed, days_in_month):
    if days_passed == 0 or days_passed >= days_in_month:
        return fact_value
    return fact_value / days_passed * days_in_month


def status_for(fact, plan, direction):
    if plan == 0:
        return "—"
    delta_pct = (fact - plan) / plan * 100 if plan != 0 else 0
    if direction == "up":
        if fact >= plan:
            return "🟢"
        if delta_pct >= -10:
            return "🟡"
        return "🔴"
    else:
        if fact <= plan:
            return "🟢"
        if delta_pct <= 10:
            return "🟡"
        return "🔴"


def write_kpi(sh, month_str, plan_total, fact):
    try:
        ws = sh.worksheet(KPI_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=KPI_SHEET, rows=50, cols=10)

    values = [
        [f"KPI — {month_str} (прошло {fact['days_passed']} из {fact['days_in_month']} дней)", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
        ["KPI", "План (ИТОГО)", "Факт", "Прогноз", "Δ абс", "Δ %", "Статус"],
        ["", "", "", "", "", "", ""],
    ]

    for key, name, unit, direction in KPI_LIST:
        plan_val = plan_total.get(key)
        fact_val = fact.get(key, 0)
        if plan_val is None:
            values.append([name, "—", round(fact_val, 2), "—", "—", "—", "—"])
            continue
        forecast_val = forecast_month(fact_val, fact["days_passed"], fact["days_in_month"])
        delta_abs = fact_val - plan_val
        delta_pct = (delta_abs / plan_val * 100) if plan_val != 0 else 0
        status = status_for(forecast_val, plan_val, direction)
        values.append([name, round(plan_val, 2), round(fact_val, 2),
                       round(forecast_val, 2), round(delta_abs, 2),
                       round(delta_pct, 1), status])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    logger.info("Лист «KPI» обновлён за %s", month_str)


def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    plans = read_plan(sh)
    if not plans:
        logger.warning("Нет планов в листе «План»")
        return

    # Приоритет: текущий месяц, если он есть в плане; иначе последний прошедший
    today = date.today()
    current_month = today.strftime("%Y-%m")
    if current_month in plans:
        target_month = current_month
    else:
        past_months = [m for m in plans.keys() if m <= current_month]
        target_month = max(past_months) if past_months else max(plans.keys())
    logger.info("Считаю KPI за %s (текущий: %s)", target_month, current_month)

    plan_total = plans.get(target_month, {}).get("ИТОГО", {})
    fact = calc_fact(target_month)
    write_kpi(sh, target_month, plan_total, fact)

    logger.info("Факт: выручка %s (активные %s, распродажа %s), прибыль %s, маржа %s%%",
                fact["revenue_total"], fact["revenue_active"],
                fact["revenue_liq"], fact["profit_total"], fact["margin_total"])
    logger.info("Неликвид в товаре: %s%%, доля активных в выручке: %s%%, распродано SKU: %s",
                fact["liq_share_stock"], fact["active_share_revenue"], fact["liq_sold_skus"])


if __name__ == "__main__":
    main()
