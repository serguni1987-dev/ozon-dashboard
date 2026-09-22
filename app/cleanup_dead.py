"""
cleanup_dead.py — аудит мёртвых SKU (показов много, заказов ноль).
Раскладывает по причинам и экспортирует в CSV.
"""
import sqlite3
import csv
from datetime import datetime, timedelta

DB = "ozon.db"
OUT_CSV = "dead_skus.csv"

DEAD_VIEWS_MIN = 100
DEAD_ORDERS_MAX = 0


def to_int_safe(v):
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def classify(r):
    """
    Приоритеты:
      1. stock = 0                        → out_of_stock
      2. views < 200                      → low_traffic
      3. pdp < 5% от views                → no_pdp (не заходят в карточку)
      4. pdp > 0, но заказов 0            → low_conv (заходят, но не покупают)
      5. price_idx = дорогой              → price_issue
      6. иначе                            → poor_position
    """
    views = r["views"] or 0
    pdp = r["pdp"] or 0
    price_idx = r["price_idx"]
    stock_val = to_int_safe(r["stock"])

    # 1. Нет остатка
    if stock_val is not None and stock_val <= 0:
        return ("out_of_stock", "нет остатка",
                "Заказать или скрыть из выдачи")

    # 2. Мало данных
    if views < 200:
        return ("low_traffic", "мало показов",
                "Реклама, акции, бустинг")

    # 3. Показы есть, но в карточку почти не заходят
    if views >= 200 and pdp < views * 0.05:
        return ("no_pdp", "не заходят в карточку",
                "Главное фото, заголовок, категория")

    # 4. В карточку заходят, но не покупают
    if pdp > 0:
        if price_idx and any(s in str(price_idx).lower() for s in ["дорог"]):
            return ("price_issue", f"цена: {price_idx}",
                    "Снизить цену или усилить описание")
        return ("low_conv", "заходят, но не покупают",
                "Цена, описание, отзывы, фото")

    # 5. Запасной вариант
    return ("poor_position", "плохая позиция",
            "SEO: название, ключи, характеристики")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if not max_date:
        print("Нет данных.")
        return
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT p.offer_id, p.name, p.category_l3, p.brand,
               SUM(sd.views_total)   AS views,
               SUM(sd.pdp_visits)    AS pdp,
               AVG(sd.position_search) AS pos,
               MAX(sd.price_index)   AS price_idx,
               MAX(sd.stock)         AS stock,
               MAX(sd.discount_pct)  AS discount,
               MAX(sd.avg_price)     AS avg_price,
               SUM(sd.orders_units)  AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
        HAVING views >= ? AND orders <= ?
        ORDER BY views DESC
    """, (date_from, max_date, DEAD_VIEWS_MIN, DEAD_ORDERS_MAX)).fetchall()

    print("=" * 130)
    print(f"АУДИТ МЁРТВЫХ SKU   |   период {date_from} — {max_date}")
    print("=" * 130)
    print(f"\n  Всего мёртвых SKU: {len(rows)}")
    total_views = sum(r["views"] for r in rows)
    total_pdp = sum(r["pdp"] or 0 for r in rows)
    print(f"  Суммарно показов впустую:  {total_views:,}")
    print(f"  Суммарно заходов в карточку: {total_pdp:,}")
    if total_views:
        print(f"  Доля заходов в карточку:   {total_pdp / total_views * 100:.1f}%")

    buckets = {}
    enriched = []
    for r in rows:
        reason_code, reason_text, action_text = classify(r)
        buckets.setdefault(reason_code, []).append(r)
        enriched.append((r, reason_code, reason_text, action_text))

    print(f"\n  Группы по причинам:")
    print("  " + "-" * 80)
    order = ["out_of_stock", "no_pdp", "low_conv", "price_issue",
             "poor_position", "low_traffic"]
    for code in order:
        group = buckets.get(code, [])
        if not group:
            continue
        views = sum(r["views"] for r in group)
        pdp = sum(r["pdp"] or 0 for r in group)
        print(f"  {code:<15} {len(group):>4} SKU  |  показов: {views:>7,}  |  "
              f"заходов: {pdp:>6,}  |  доля: {pdp/views*100 if views else 0:>5.1f}%")

    print(f"\n  ТОП-20 по показам — что делать:")
    print("  " + "-" * 128)
    print(f"  {'Offer ID':<18} {'Название':<34} {'Показы':>7} {'Зах':>6} "
          f"{'Доля':>6} {'Поз':>6} {'Цена':>14} {'Ост':>4} {'Причина':<13} {'Действие':<28}")
    print("  " + "-" * 128)

    for r, code, reason_text, action_text in enriched[:20]:
        name = (r["name"] or "")[:33]
        price = (r["price_idx"] or "—")[:14]
        pos = f"{r['pos']:.0f}" if r["pos"] is not None else "—"
        stock = r["stock"] if r["stock"] is not None else "—"
        views = r["views"] or 0
        pdp = r["pdp"] or 0
        share = pdp / views * 100 if views else 0
        print(f"  {r['offer_id']:<18} {name:<34} {views:>7} {pdp:>6} "
              f"{share:>5.1f}% {pos:>6} {price:>14} {str(stock):>4} {code:<13} {action_text:<28}")

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "offer_id", "name", "category_l3", "brand",
            "views", "pdp_visits", "pdp_share_pct", "avg_position",
            "price_index", "stock", "discount_pct", "avg_price",
            "reason_code", "reason_text", "action"
        ])
        for r, code, reason_text, action_text in enriched:
            views = r["views"] or 0
            pdp = r["pdp"] or 0
            share = pdp / views * 100 if views else 0
            w.writerow([
                r["offer_id"], r["name"], r["category_l3"], r["brand"],
                views, pdp, f"{share:.1f}",
                f"{r['pos']:.0f}" if r["pos"] is not None else "",
                r["price_idx"], r["stock"], r["discount"], r["avg_price"],
                code, reason_text, action_text,
            ])

    print(f"\n  CSV сохранён: {OUT_CSV}")
    print(f"  Откройте в Excel. Разделитель ';', кодировка UTF-8 с BOM.")
    print("=" * 130)

    con.close()


if __name__ == "__main__":
    main()
