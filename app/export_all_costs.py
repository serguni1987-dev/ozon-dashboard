"""
export_all_costs.py — выгружает все свои SKU в проект/costs_all.csv.
Формат: offer_id;sku;name;category_l2;cost_price;date_from;cost_price_new;date_from_new
Колонки 5-6 (cost_price, date_from) — текущая цена (справочно).
Колонки 7-8 (cost_price_new, date_from_new) — для НОВОЙ цены (заполни, если хочешь изменить).
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
          "cost_price", "date_from", "cost_price_new", "date_from_new"]


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if max_date:
        date_from_30d = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        date_from_30d = "1900-01-01"

    rows = con.execute("""
        SELECT
            p.sku, p.offer_id, p.name, p.category_l2,
            p.cost_price AS products_cost, p.cost_date AS products_date,
            (SELECT cost_price FROM product_cost_history
             WHERE sku = p.sku ORDER BY date_from DESC LIMIT 1) AS last_price,
            (SELECT date_from FROM product_cost_history
             WHERE sku = p.sku ORDER BY date_from DESC LIMIT 1) AS last_date,
            COALESCE(SUM(sd.revenue), 0)      AS revenue_30d,
            COALESCE(SUM(sd.orders_units), 0) AS orders_30d,
            COALESCE(SUM(sd.views_total), 0)  AS views_30d,
            COALESCE(MAX(sd.avg_price), 0)    AS last_sale_price
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
            cost = r["last_price"] if r["last_price"] else r["products_cost"]
            dt = r["last_date"] if r["last_date"] else (r["products_date"] or "2026-01-01")
            w.writerow([
                r["offer_id"] or "",
                r["sku"],
                (r["name"] or "")[:200],
                r["category_l2"] or "",
                f"{cost:.2f}" if cost else "",
                dt,
                "",   # cost_price_new — ЗАПОЛНИ, если хочешь изменить
                "",   # date_from_new — ЗАПОЛНИ дату начала действия
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
                r["last_price"] if r["last_price"] else (r["products_cost"] or ""),
                f"{r['revenue_30d']:.0f}",
                r["orders_30d"], r["views_30d"],
                f"{r['last_sale_price']:.0f}", prio,
            ])

    sold = sum(1 for r in rows if r["revenue_30d"] > 0)
    with_views = sum(1 for r in rows if r["views_30d"] > 0 and r["revenue_30d"] == 0)
    silent = sum(1 for r in rows if r["views_30d"] == 0 and r["revenue_30d"] == 0)
    has_cost = sum(1 for r in rows if r["last_price"] or r["products_cost"])

    print(f"\nРаспределение:")
    print(f"  Продавались за 30 дней:      {sold:>5}")
    print(f"  Были показы, без продаж:     {with_views:>5}")
    print(f"  Совсем тихие:                {silent:>5}")
    print(f"  Уже с себестоимостью:        {has_cost:>5}")

    con.close()


if __name__ == "__main__":
    main()