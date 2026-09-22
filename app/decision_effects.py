"""
decision_effects.py v2 — дневник решений с честным сравнением.
"До" = 30 дней до решения. "После" = от решения до последней даты в базе.
"""
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
TAX_PCT        = 0.15

# Минимум дней после решения, чтобы выносить вердикт
MIN_DAYS_FOR_VERDICT = 3
# Сколько дней "до" считаем
BEFORE_DAYS = 30


def money(x):
    return f"{x:>12,.0f} ₽"


def pct(x):
    return f"{x*100:>6.1f}%"


def get_period_metrics(con, sku, cost_price, date_from, date_to):
    """Метрики за произвольный период."""
    if date_from > date_to:
        return None

    agg = con.execute("""
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    """, (sku, date_from, date_to)).fetchone()

    price_row = con.execute("""
        SELECT AVG(avg_price) AS p FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ? AND orders_units > 0
    """, (sku, date_from, date_to)).fetchone()

    rev = agg["rev"] or 0
    orders = agg["orders"] or 0
    cost = (cost_price or 0) * orders
    comm = rev * COMMISSION_PCT
    serv = rev * SERVICES_PCT
    pb = rev - cost - comm - serv
    tax = pb * TAX_PCT if pb > 0 else 0
    profit = pb - tax
    margin = profit / rev if rev else 0

    return {
        "rev": rev, "orders": orders,
        "views": agg["views"] or 0, "carts": agg["carts"] or 0,
        "price": price_row["p"] if price_row and price_row["p"] else 0,
        "profit": profit, "margin": margin,
    }


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]

    rows = con.execute("""
        SELECT id, created_at, offer_id, category, action_text,
               status, note
        FROM decisions
        ORDER BY created_at DESC
    """).fetchall()

    print("=" * 122)
    print(f"ДНЕВНИК РЕШЕНИЙ  |  данные в базе до {max_date}")
    print("=" * 122)

    if not rows:
        print("\n  Решений пока нет.")
        con.close()
        return

    in_progress = sum(1 for r in rows if r["status"] == "in_progress")
    print(f"\n  Всего решений: {len(rows)}  (в работе: {in_progress})\n")

    for r in rows:
        created_date = r["created_at"][:10]
        days_since = (datetime.now() - datetime.strptime(created_date, "%Y-%m-%d")).days

        # Метаданные SKU
        prod = con.execute(
            "SELECT sku, cost_price FROM products WHERE offer_id = ?",
            (r["offer_id"],)
        ).fetchone()
        if not prod:
            print(f"  #{r['id']} {r['offer_id']}: SKU не найден\n")
            continue

        # Окно "До": BEFORE_DAYS дней до решения
        before_to = (datetime.strptime(created_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        before_from = (datetime.strptime(created_date, "%Y-%m-%d") - timedelta(days=BEFORE_DAYS)).strftime("%Y-%m-%d")
        before = get_period_metrics(con, prod["sku"], prod["cost_price"], before_from, before_to)

        # Окно "После": от решения до max_date в базе
        after_from = created_date
        after_to = max_date
        after = None
        after_days = 0
        if after_from <= after_to:
            after = get_period_metrics(con, prod["sku"], prod["cost_price"], after_from, after_to)
            after_days = (datetime.strptime(after_to, "%Y-%m-%d") - datetime.strptime(after_from, "%Y-%m-%d")).days + 1

        # Вердикт
        if after is None or after["orders"] == 0 and after["views"] == 0:
            if created_date > max_date:
                verdict = f"⏳ ждём данных (база отстаёт)"
            elif after_days < MIN_DAYS_FOR_VERDICT:
                verdict = f"⏳ рано судить ({after_days} дн данных)"
            else:
                verdict = "❓ нет активности после решения"
        elif after_days < MIN_DAYS_FOR_VERDICT:
            verdict = f"⏳ рано судить ({after_days} дн данных)"
        else:
            profit_delta = after["profit"] - before["profit"] / BEFORE_DAYS * after_days if before else 0
            if after["profit"] > 0 and (before["profit"] if before else 0) < 0:
                verdict = "✅ вышли из убытка"
            elif after["profit"] > (before["profit"] / BEFORE_DAYS * after_days if before else 0):
                verdict = "✅ прибыль выше прежнего темпа"
            elif after["orders"] < (before["orders"] / BEFORE_DAYS * after_days if before else 0) * 0.7:
                verdict = "❌ заказов стало меньше"
            else:
                verdict = "➖ нейтрально"

        print(f"  {'─' * 118}")
        print(f"  #{r['id']}  {r['created_at'][:16]}  ({days_since} дн назад)   {verdict}")
        print(f"  SKU:      {r['offer_id']}")
        print(f"  Действие: {r['action_text']}")
        if r["category"]:
            print(f"  Категория: {r['category']}")
        print()

        if after is None:
            if before:
                print(f"  Данных «после» ещё нет. «До»: {before['orders']} заказов, "
                      f"прибыль {before['profit']:,.0f} ₽/30д.")
            print()
            continue

        if not before and not after:
            print("  Нет данных ни до, ни после.\n")
            continue

        print(f"  {'Метрика':<14} {'До (30д)':>13} {'После':>13} {'Δ':>10}")
        print(f"  {'-' * 52}")

        def line(label, b_key, a_key, fmt="num"):
            b = before[b_key] if before else 0
            a = after[a_key] if after else 0
            if fmt == "money":
                bs = f"{b:>11,.0f} ₽"; as_ = f"{a:>11,.0f} ₽"
            elif fmt == "pct":
                bs = f"{b*100:>11.1f}%"; as_ = f"{a*100:>11.1f}%"
            else:
                bs = f"{b:>13,}"; as_ = f"{a:>13,}"
            delta = ""
            if b:
                d = (a - b) / abs(b) * 100
                delta = f"{d:+.0f}%"
            print(f"  {label:<14} {bs} {as_} {delta:>10}")

        line("Заказы",   "orders", "orders")
        line("Выручка",  "rev",    "rev",   "money")
        line("Прибыль",  "profit", "profit","money")
        line("Маржа",    "margin", "margin","pct")
        line("Ср. цена", "price",  "price", "money")
        line("Показы",   "views",  "views")
        line("Корзины",  "carts",  "carts")

        if after_days > 0 and before:
            # Пересчёт "до" к длине "после" (чтобы честно сравнить)
            coef = after_days / BEFORE_DAYS
            expected_profit = before["profit"] * coef
            actual_profit = after["profit"]
            effect = actual_profit - expected_profit
            print(f"\n  Эффект за {after_days} дн: "
                  f"ожидали {expected_profit:,.0f} ₽, получили {actual_profit:,.0f} ₽ "
                  f"→ {effect:+,.0f} ₽")

    print("=" * 122)
    con.close()


if __name__ == "__main__":
    main()
