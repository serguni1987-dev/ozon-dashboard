"""
plan_core.py — общий модуль для расчёта плана действий.
Используется в daily_dashboard.py и action_plan.py.
"""
import sqlite3
from datetime import datetime, timedelta

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
TAX_PCT        = 0.15
AVG_CHECK      = 6285
TARGET_MARGIN  = 0.15


def calc_margin(rev, orders, cost_price):
    cost_total = (cost_price or 0) * orders
    comm = rev * COMMISSION_PCT
    serv = rev * SERVICES_PCT
    pb = rev - cost_total - comm - serv
    tax = pb * TAX_PCT if pb > 0 else 0
    profit = pb - tax
    margin = profit / rev if rev else 0
    denom = 1 - COMMISSION_PCT - SERVICES_PCT - TARGET_MARGIN
    target = (cost_price or 0) / denom if denom > 0 else 0
    return profit, margin, cost_total, target


def get_actions(con, date_from, date_to):
    """Возвращает список действий, ранжированных по эффекту."""
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT p.sku, p.offer_id, p.name, p.cost_price,
               COALESCE(SUM(sd.revenue), 0)         AS revenue,
               COALESCE(SUM(sd.orders_units), 0)    AS orders,
               COALESCE(SUM(sd.pdp_visits), 0)      AS pdp,
               COALESCE(SUM(sd.cart_adds_total), 0) AS carts,
               COALESCE(SUM(sd.views_total), 0)     AS views
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (date_from, date_to)).fetchall()

    actions = []
    for r in rows:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        pdp = r["pdp"] or 0
        carts = r["carts"] or 0
        cost_price = r["cost_price"] or 0

        profit, margin, cost_total, target = calc_margin(rev, orders, cost_price)

        category = None
        action_text = ""
        effect = 0.0
        priority = 9

        if orders > 0 and profit < 0:
            cur_price = rev / orders
            category = "УБЫТОЧНЫЙ"
            action_text = f"Поднять цену с {cur_price:,.0f} до {target:,.0f} ₽ или снять"
            effect = -profit
            priority = 1
        elif orders > 0 and margin < 0.05:
            cur_price = rev / orders
            category = "КРИТ. МАРЖА"
            action_text = f"Поднять цену с {cur_price:,.0f} до {target:,.0f} ₽"
            effect = max(0, profit * 0.8)
            priority = 3
        elif orders == 0 and carts >= 3:
            category = "ДОСТАВКА"
            action_text = f"Проверить доставку: {carts} корзин без заказа"
            effect = carts * 0.3 * AVG_CHECK
            priority = 2
        elif orders == 0 and pdp >= 30:
            category = "КАРТОЧКА"
            action_text = f"Переделать карточку: {pdp} заходов без заказа"
            effect = pdp * 0.005 * AVG_CHECK
            priority = 4
        elif orders > 0 and margin >= 0.25:
            category = "МАСШТАБ"
            action_text = f"Масштабировать: маржа {margin*100:.1f}%"
            effect = profit * 0.10
            priority = 5

        if category is None:
            continue

        actions.append({
            "offer_id": r["offer_id"],
            "name": r["name"],
            "category": category,
            "priority": priority,
            "current": (f"маржа {margin*100:>5.1f}%, приб {profit:>7,.0f} ₽, "
                        f"зак {orders}, корз {carts}, зах {pdp}"),
            "action": action_text,
            "effect": effect,
        })

    actions.sort(key=lambda x: (x["priority"], -x["effect"]))
    return actions
