"""
hot_carts.py — SKU, где были корзины, но нет заказов.
Это самые горячие лиды: клиенты почти купили.
"""
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"
MIN_CARTS = 3


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT p.offer_id, p.name, p.cost_price, p.category_l3,
               SUM(sd.views_total)     AS views,
               SUM(sd.pdp_visits)      AS pdp,
               SUM(sd.cart_adds_total) AS carts,
               SUM(sd.orders_units)    AS orders,
               AVG(sd.avg_price)       AS avg_price,
               AVG(sd.position_search) AS avg_pos,
               MAX(sd.price_index)     AS price_idx,
               MAX(sd.stock)           AS stock
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
        HAVING SUM(sd.cart_adds_total) >= ?
           AND SUM(sd.orders_units) = 0
        ORDER BY carts DESC
    """, (date_from, max_date, MIN_CARTS)).fetchall()

    print("=" * 130)
    print(f"БРОШЕННЫЕ КОРЗИНЫ (>= {MIN_CARTS}) — период {date_from} — {max_date}")
    print("=" * 130)

    if not rows:
        print("\n  Нет SKU с корзинами без заказов.")
        con.close()
        return

    total_carts = sum(r["carts"] for r in rows)
    print(f"\n  Всего SKU: {len(rows)}")
    print(f"  Всего брошенных корзин: {total_carts}")

    print(f"\n  {'Offer ID':<18} {'Название':<38} {'Корз':>5} {'Зах':>5} "
          f"{'Поз':>5} {'Себест':>8} {'Цена':>8} {'Цена-индекс':<14} {'Ост':>4}")
    print("  " + "-" * 126)

    for r in rows:
        name = (r["name"] or "")[:37]
        cost = f"{r['cost_price']:,.0f}" if r["cost_price"] else "—"
        price = f"{r['avg_price']:,.0f}" if r["avg_price"] else "—"
        pos = f"{r['avg_pos']:.0f}" if r["avg_pos"] is not None else "—"
        price_idx = (r["price_idx"] or "—")[:14]
        stock = r["stock"] if r["stock"] is not None else "—"

        print(f"  {r['offer_id']:<18} {name:<38} {r['carts']:>5} {r['pdp']:>5} "
              f"{pos:>5} {cost:>8} {price:>8} {price_idx:<14} {str(stock):>4}")

    print("=" * 130)
    print("\n  Действие: проверить в ЛК Ozon брошенные корзины и условия доставки.")
    print("            Для габаритных — рассмотреть альтернативную упаковку.")
    print("=" * 130)

    con.close()


if __name__ == "__main__":
    main()
