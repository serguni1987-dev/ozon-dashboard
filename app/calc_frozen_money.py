"""
calc_frozen_money.py — анализ заморозки денег в складе.
Данные из current_stocks (актуальные остатки из Ozon API).
"""
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cs.offer_id, cs.total_present AS stock,
               cs.fbo_present, cs.fbs_present,
               p.name, p.category_l3, p.cost_price,
               COALESCE(sd.orders, 0)  AS orders_30d,
               COALESCE(sd.rev, 0)     AS rev_30d,
               cp.price                 AS current_price,
               cp.price_index_color     AS color
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN current_prices cp ON cp.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders, SUM(revenue) AS rev
            FROM sales_daily WHERE date >= ?
            GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        stock = r["stock"] or 0
        cost = r["cost_price"] or 0
        frozen = stock * cost
        orders = r["orders_30d"] or 0
        days = stock / (orders / 30) if orders > 0 else 999

        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:50],
            "category": r["category_l3"] or "",
            "stock": int(stock),
            "fbo": int(r["fbo_present"] or 0),
            "fbs": int(r["fbs_present"] or 0),
            "cost": cost,
            "frozen": frozen,
            "orders_30d": orders,
            "days_to_sell": days,
            "current_price": r["current_price"] or 0,
            "color": r["color"] or "",
        })

    items.sort(key=lambda x: -x["frozen"])

    total_frozen = sum(i["frozen"] for i in items)
    dead_items = [i for i in items if i["orders_30d"] == 0]
    dead_money = sum(i["frozen"] for i in dead_items)

    # Приоритет: заморожено × дней (но не больше 365)
    priority = sorted(
        items,
        key=lambda x: -(x["frozen"] * min(x["days_to_sell"], 365) / 1000)
    )

    print("=" * 135)
    print(f"ЗАМОРОЗКА В СКЛАДЕ  |  актуальные остатки из Ozon API")
    print("=" * 135)
    print(f"\n  SKU с остатком:        {len(items)}")
    print(f"  Всего заморожено:      {total_frozen:>14,.0f} ₽")
    print(f"  Мёртвые (0 продаж 30д): {len(dead_items)} SKU  →  {dead_money:>14,.0f} ₽  "
          f"({dead_money / total_frozen * 100:.0f}% всей заморозки)")

    print(f"\n  ТОП-30 по заморозке:")
    print(f"  {'#':<3} {'Offer ID':<18} {'Название':<44} {'Ост':>5} {'Себест':>8} "
          f"{'Замор':>11} {'Зак':>5} {'Дней':>6} {'Индекс':<10}")
    print("  " + "-" * 125)

    for i, it in enumerate(items[:30], 1):
        days_str = f"{it['days_to_sell']:.0f}" if it['days_to_sell'] < 999 else "∞"
        print(f"  {i:<3} {it['offer_id']:<18} {it['name']:<44} {it['stock']:>5} "
              f"{it['cost']:>8,.0f} {it['frozen']:>10,.0f} ₽ "
              f"{it['orders_30d']:>5} {days_str:>6} {it['color']:<10}")

    print(f"\n  ЧТО ВЫСВОБОДИТЬ ПЕРВЫМ (топ-15 по формуле заморожено × дней):")
    print(f"  {'#':<3} {'Offer ID':<18} {'Название':<44} {'Замор':>11} "
          f"{'Дней':>6} {'Заказов':>8} {'Индекс':<10}")
    print("  " + "-" * 110)

    for i, it in enumerate(priority[:15], 1):
        days_str = f"{it['days_to_sell']:.0f}" if it['days_to_sell'] < 999 else "∞"
        print(f"  {i:<3} {it['offer_id']:<18} {it['name']:<44} "
              f"{it['frozen']:>10,.0f} ₽ {days_str:>6} {it['orders_30d']:>8} {it['color']:<10}")

    top15_sum = sum(i["frozen"] for i in priority[:15])
    print()
    print("=" * 135)
    print(f"  ИТОГ:")
    print(f"    Топ-15 = {top15_sum:,.0f} ₽  =  {top15_sum / total_frozen * 100:.0f}% всей заморозки")
    print("=" * 135)

    con.close()


if __name__ == "__main__":
    main()
