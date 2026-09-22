"""
drill_sku.py — воронка по одному SKU.
Использование: py drill_sku.py OVL0492402602
"""
import sys
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"


def main():
    if len(sys.argv) < 2:
        print("Использование: py drill_sku.py <offer_id>")
        print("Пример:        py drill_sku.py OVL0492402602")
        return

    offer_id = sys.argv[1]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    prod = con.execute(
        "SELECT sku, offer_id, name, category_l3, brand, cost_price "
        "FROM products WHERE offer_id = ?",
        (offer_id,)
    ).fetchone()

    if not prod:
        print(f"SKU {offer_id} не найден в products.")
        return

    print("=" * 110)
    print(f"ВОРОНКА SKU {offer_id}")
    print("=" * 110)
    print(f"\n  Название:      {prod['name']}")
    print(f"  Категория:     {prod['category_l3']}")
    print(f"  Бренд:         {prod['brand']}")
    print(f"  Себестоимость: {prod['cost_price']} ₽")

    max_date = con.execute("SELECT MAX(date) FROM sales_daily WHERE sku = ?",
                           (prod["sku"],)).fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    agg = con.execute("""
        SELECT
            SUM(views_total)          AS views,
            SUM(visitors_total)       AS visitors,
            SUM(pdp_visits)           AS pdp,
            SUM(pdp_visitors)         AS pdp_vis,
            SUM(cart_adds_total)      AS carts,
            SUM(orders_units)         AS orders,
            SUM(revenue)              AS revenue,
            AVG(avg_price)            AS avg_price,
            AVG(position_search)      AS avg_pos,
            MAX(price_index)          AS price_idx,
            SUM(days_in_promo)        AS promo_days,
            SUM(days_with_ads)        AS ad_days,
            MAX(stock)                AS stock
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    """, (prod["sku"], date_from, max_date)).fetchone()

    views = agg["views"] or 0
    visitors = agg["visitors"] or 0
    pdp = agg["pdp"] or 0
    pdp_vis = agg["pdp_vis"] or 0
    carts = agg["carts"] or 0
    orders = agg["orders"] or 0
    revenue = agg["revenue"] or 0
    avg_price = agg["avg_price"] or 0
    avg_pos = agg["avg_pos"]
    price_idx = agg["price_idx"] or "—"
    promo = agg["promo_days"] or 0
    ads = agg["ad_days"] or 0
    stock = agg["stock"]

    def pct(a, b):
        return f"{a/b*100:>5.1f}%" if b else "  —  "

    print(f"  Остаток:       {stock if stock is not None else '—'}")
    print(f"\n  Период: {date_from} — {max_date} (30 дней)")
    print(f"\n  ВОРОНКА:")
    print(f"    Показы:             {views:>8,}")
    print(f"    Посетители:         {visitors:>8,}")
    print(f"    Заходы в карточку:  {pdp:>8,}   (от показов: {pct(pdp, views)})")
    print(f"    Добавили в корзину: {carts:>8,}   (от заходов: {pct(carts, pdp)})")
    print(f"    Заказы:             {orders:>8,}   (от корзин: {pct(orders, carts)})")
    print(f"    Выручка:            {revenue:>8,.0f} ₽")
    print(f"    Средняя цена:       {avg_price:>8,.0f} ₽")
    print(f"\n  ПОЗИЦИЯ и ЦЕНА:")
    if avg_pos:
        print(f"    Средняя позиция:    {avg_pos:.0f}")
    else:
        print(f"    Средняя позиция:    —")
    print(f"    Индекс цены:        {price_idx}")
    print(f"    Дней в акции:       {promo}")
    print(f"    Дней с рекламой:    {ads}")

    print(f"\n  ПО ДНЯМ (только дни с показами > 0):")
    print("  " + "-" * 100)
    print(f"  {'Дата':<12} {'Показы':>8} {'Заходы':>8} {'Корзины':>8} "
          f"{'Заказы':>7} {'Позиция':>8} {'Цена':>10}")
    print("  " + "-" * 100)

    daily = con.execute("""
        SELECT date, views_total, pdp_visits, cart_adds_total, orders_units,
               position_search, avg_price
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
        ORDER BY date
    """, (prod["sku"], date_from, max_date)).fetchall()

    for r in daily:
        if (r["views_total"] or 0) == 0:
            continue
        pos = f"{r['position_search']}" if r["position_search"] else "—"
        price = f"{r['avg_price']:,.0f}" if r["avg_price"] else "—"
        print(f"  {r['date']:<12} {r['views_total'] or 0:>8} {r['pdp_visits'] or 0:>8} "
              f"{r['cart_adds_total'] or 0:>8} {r['orders_units'] or 0:>7} "
              f"{pos:>8} {price:>10}")

    print("=" * 110)
    con.close()


if __name__ == "__main__":
    main()
