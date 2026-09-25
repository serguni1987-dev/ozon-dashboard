"""
export_all_costs.py — экспорт ВСЕХ своих SKU в проект/costs_all.csv
для заполнения себестоимости + справочный файл costs_all_info.csv.

Формат costs_all.csv: offer_id;sku;name;category_l2;cost_price;date_from;comment
Совместим с import_costs.py (читает date_from, пишет в product_cost_history).
"""
import csv
import sqlite3
import os
from datetime import datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
DB = os.path.join(APP_DIR, "ozon.db")
OUT_MAIN = os.path.join(PROJECT_DIR, "costs_all.csv")
OUT_INFO = os.path.join(PROJECT_DIR, "costs_all_info.csv")

HEADER = ["offer_id", "sku", "name", "category_l2",
          "cost_price", "date_from", "comment"]


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if max_date:
        date_from_30d = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        date_from_30d = "1900-01-01"

    rows = con.execute("""
        SELECT p.sku, p.offer_id, p.name, p.category_l2,
               p.cost_price, p.cost_date,
               COALESCE(SUM(sd.revenue), 0)      AS revenue_30d,
               COALESCE(SUM(sd.orders_units), 0) AS orders_30d,
               COALESCE(SUM(sd.views_total), 0)  AS views_30d,
               COALESCE(MAX(sd.avg_price), 0)    AS last_price
        FROM products p
        LEFT JOIN sales_daily sd
               ON sd.sku = p.sku
              AND sd.date BETWEEN ? AND ?
        WHERE p.is_own = 1
        GROUP BY p.sku
        ORDER BY revenue_30d DESC, orders_30d DESC, views_30d DESC, p.offer_id
    """, (date_from_30d, max_date)).fetchall()

    print(f"Всего своих SKU: {len(rows)}")
    print(f"Период агрегатов: {date_from_30d} — {max_date}")

    written = 0
    with open(OUT_MAIN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(HEADER)
        for r in rows:
            w.writerow([
                r["offer_id"] or "",
                r["sku"],
                (r["name"] or "")[:200],
                r["category_l2"] or "",
                f"{r['cost_price']:.2f}" if r["cost_price"] else "",
                r["cost_date"] or "2026-01-01",
                "",
            ])
            written += 1

    print(f"\nЗаписано в {OUT_MAIN}: {written} строк")

    # Справочный файл
    with open(OUT_INFO, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["offer_id", "name", "category_l2",
                    "cost_price_now", "revenue_30d", "orders_30d",
                    "views_30d", "last_price", "priority"])
        for r in rows:
            if r["revenue_30d"] > 0:
                prio = "1_PRODAETSYA"
            elif r["views_30d"] > 0:
                prio = "2_EST_POKAZY"
            else:
                prio = "3_TIHIY"
            w.writerow([
                r["offer_id"], r["name"], r["category_l2"],
                r["cost_price"] if r["cost_price"] is not None else "",
                f"{r['revenue_30d']:.0f}",
                r["orders_30d"], r["views_30d"],
                f"{r['last_price']:.0f}", prio,
            ])

    sold = sum(1 for r in rows if r["revenue_30d"] > 0)
    with_views = sum(1 for r in rows if r["views_30d"] > 0 and r["revenue_30d"] == 0)
    silent = sum(1 for r in rows if r["views_30d"] == 0 and r["revenue_30d"] == 0)
    has_cost = sum(1 for r in rows if r["cost_price"] is not None)

    print(f"\nРаспределение:")
    print(f"  Продавались за 30 дней:      {sold:>5}")
    print(f"  Были показы, но без продаж:  {with_views:>5}")
    print(f"  Совсем тихие:                {silent:>5}")
    print(f"  Уже с себестоимостью:        {has_cost:>5}")

    print(f"\nГотово.")
    print(f"  {OUT_MAIN}  — редактируй тут")
    print(f"  {OUT_INFO}  — справочно")

    con.close()


if __name__ == "__main__":
    main()