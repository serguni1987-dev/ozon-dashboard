"""
add_decision.py — добавить решение в дневник.
Использование:
  py add_decision.py --offer=OCE013E4 --category=УБЫТОЧНЫЙ --action="Поднял цену до 7100" --price=7100
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
TAX_PCT        = 0.15


def parse_args():
    args = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if "=" in arg:
                k, v = arg[2:].split("=", 1)
                args[k] = v
            else:
                args[arg[2:]] = True
    return args


def main():
    args = parse_args()

    offer_id = args.get("offer")
    if not offer_id:
        print("Использование: py add_decision.py --offer=OCE013E4 --category=... --action=\"...\" [--price=7100]")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    prod = con.execute(
        "SELECT sku, name, cost_price FROM products WHERE offer_id = ?",
        (offer_id,)
    ).fetchone()
    if not prod:
        print(f"SKU {offer_id} не найден.")
        return

    # Снимок метрик за последние 30 дней
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    agg = con.execute("""
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    """, (prod["sku"], date_from, max_date)).fetchone()

    # Средняя цена — только по дням с заказами, иначе нули занижают
    price_row = con.execute("""
        SELECT AVG(avg_price) AS p FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ? AND orders_units > 0
    """, (prod["sku"], date_from, max_date)).fetchone()
    avg_price = price_row["p"] if price_row else None

    rev = agg["rev"] or 0
    orders = agg["orders"] or 0
    cost = (prod["cost_price"] or 0) * orders
    comm = rev * COMMISSION_PCT
    serv = rev * SERVICES_PCT
    pb = rev - cost - comm - serv
    tax = pb * TAX_PCT if pb > 0 else 0
    profit = pb - tax
    margin = profit / rev if rev else 0

    price_before = avg_price or 0
    price_after = float(args.get("price", 0)) or None

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    review_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    con.execute("""
        INSERT INTO decisions
        (created_at, offer_id, category, action_text,
         revenue_before, profit_before, margin_before, orders_before,
         views_before, carts_before, price_before, price_after,
         status, review_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?)
    """, (
        now, offer_id,
        args.get("category", ""),
        args.get("action", ""),
        rev, profit, margin, orders,
        agg["views"] or 0, agg["carts"] or 0,
        price_before, price_after,
        review_at,
    ))
    con.commit()

    print(f"[OK] Решение добавлено (id={con.execute('SELECT last_insert_rowid()').fetchone()[0]})")
    print(f"  SKU:       {offer_id}")
    print(f"  Действие:  {args.get('action', '')}")
    print(f"  Цена:      {price_before:,.0f} → {price_after:,.0f}" if price_after else f"  Цена:      {price_before:,.0f}")
    print(f"  Прибыль до: {profit:,.0f} ₽, маржа {margin*100:.1f}%")
    print(f"  Проверить: {review_at}")

    con.close()


if __name__ == "__main__":
    main()
