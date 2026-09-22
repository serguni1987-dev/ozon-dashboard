"""
action_plan.py v2 — план действий БЕЗ двойного счёта.
Один SKU = одна карточка действия. Приоритет по деньгам.
"""
import sqlite3
import csv
from datetime import datetime, timedelta

DB = "ozon.db"
OUT_CSV = "actions.csv"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
TAX_PCT        = 0.15
AVG_CHECK      = 6285
TARGET_MARGIN  = 0.15


def calc_margin(rev, orders, cost_price):
    """Возвращает (profit, margin, cost_total, target_price)."""
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


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    # Всё по SKU за один запрос
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
    """, (date_from, max_date)).fetchall()

    actions = []

    for r in rows:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        pdp = r["pdp"] or 0
        carts = r["carts"] or 0
        views = r["views"] or 0
        cost_price = r["cost_price"] or 0

        profit, margin, cost_total, target = calc_margin(rev, orders, cost_price)

        # Решаем, к какой категории отнести SKU — одна карточка
        # Приоритет: цена (если есть продажи и убыток/крит.маржа) → доставка → карточка → масштаб

        category = None
        action_text = ""
        effect = 0.0

        if orders > 0 and profit < 0:
            # Убыточный
            cur_price = rev / orders
            category = "УБЫТОЧНЫЙ"
            action_text = f"Поднять цену с {cur_price:,.0f} до {target:,.0f} ₽ или снять"
            effect = -profit  # убираем убыток
        elif orders > 0 and margin < 0.05:
            # Критическая маржа
            cur_price = rev / orders
            category = "КРИТ. МАРЖА"
            action_text = f"Поднять цену с {cur_price:,.0f} до {target:,.0f} ₽"
            # Реалистично: +10% цены → +~8% прибыли
            effect = max(0, profit * 0.8)
        elif orders == 0 and carts >= 3:
            # Брошенные корзины — доставка
            category = "ДОСТАВКА"
            action_text = f"Проверить доставку: {carts} корзин без заказа"
            # Реалистично: 30% корзин конвертируются
            effect = carts * 0.3 * AVG_CHECK
        elif orders == 0 and pdp >= 30:
            # Мёртвые с потенциалом — карточка
            category = "КАРТОЧКА"
            action_text = f"Переделать карточку: {pdp} заходов без заказа"
            # Реалистично: 0.5% конверсии от заходов
            effect = pdp * 0.005 * AVG_CHECK
        elif orders > 0 and margin >= 0.25:
            # Звезда
            category = "МАСШТАБ"
            action_text = f"Масштабировать: маржа {margin*100:.1f}%"
            # Реалистично: +10% выручки → +10% прибыли
            effect = profit * 0.10

        if category is None:
            continue

        actions.append({
            "offer_id": r["offer_id"],
            "name": r["name"],
            "category": category,
            "current": (f"маржа {margin*100:>5.1f}%, приб {profit:>7,.0f} ₽, "
                        f"зак {orders}, корз {carts}, зах {pdp}"),
            "action": action_text,
            "effect": effect,
        })

    # Сортировка: по эффекту, потом по категории
    priority_order = {"УБЫТОЧНЫЙ": 0, "ДОСТАВКА": 1, "КАРТОЧКА": 2, "КРИТ. МАРЖА": 3, "МАСШТАБ": 4}
    actions.sort(key=lambda x: (priority_order.get(x["category"], 9), -x["effect"]))

    print("=" * 128)
    print(f"ПЛАН ДЕЙСТВИЙ v2   |   период {date_from} — {max_date}")
    print("=" * 128)
    print(f"\n  Всего SKU к работе: {len(actions)}")
    total_effect = sum(a["effect"] for a in actions)
    print(f"  Реалистичный потенциал: {total_effect:,.0f} ₽ / 30 дней")
    print(f"  Месячная прибыль сейчас: 19 250 ₽")
    if total_effect > 0:
        print(f"  Прогноз после выполнения: {19_250 + total_effect:,.0f} ₽ "
              f"(+{total_effect/19250*100:.0f}%)")

    # По категориям
    print(f"\n  Распределение:")
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            group = cats[cat]
            grp_effect = sum(g["effect"] for g in group)
            print(f"    {cat:<12} {len(group):>3} SKU, эффект {grp_effect:>10,.0f} ₽")

    print(f"\n  {'#':<4} {'Категория':<12} {'Offer ID':<18} {'Что':<32} "
          f"{'Сейчас':<45} {'Эффект':>10}")
    print("  " + "-" * 124)

    for i, a in enumerate(actions, 1):
        name = (a["name"] or "")[:31]
        current = a["current"][:44]
        print(f"  {i:<4} {a['category']:<12} {a['offer_id']:<18} {name:<32} "
              f"{current:<45} {a['effect']:>9,.0f} ₽")

    print("=" * 128)

    # CSV
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["#", "категория", "offer_id", "название",
                    "сейчас", "что делать", "эффект ₽/мес", "сделано?"])
        for i, a in enumerate(actions, 1):
            w.writerow([i, a["category"], a["offer_id"], a["name"],
                        a["current"], a["action"], f"{a['effect']:.0f}", ""])

    print(f"\n  CSV: {OUT_CSV}")
    print("=" * 128)

    con.close()


if __name__ == "__main__":
    main()
