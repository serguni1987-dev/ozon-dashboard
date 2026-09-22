"""
export_all_costs.py — экспорт ВСЕХ своих SKU в CSV для заполнения себестоимости.
Сортирует по важности: сначала те, что продаются, потом с показами, потом остальные.
Формат файла — совместим с import_costs.py.
Плюс отдельный файл со справочной информацией (для приоритизации).
"""
import csv
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"
SRC = "costs_template.csv"      # берём заголовок отсюда
OUT_MAIN = "costs_all.csv"      # сюда заполнять себестоимость
OUT_INFO = "costs_all_info.csv" # справочная информация


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Заголовок берём из существующего шаблона
    with open(SRC, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
    print(f"Заголовок шаблона ({len(header)} колонок): {header}")

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    if max_date:
        date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        date_from = "1900-01-01"

    # Все свои SKU + агрегаты за 30 дней
    rows = con.execute("""
        SELECT p.sku, p.offer_id, p.name, p.category_l3, p.brand,
               p.cost_price,
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
    """, (date_from, max_date)).fetchall()

    print(f"Всего своих SKU: {len(rows)}")
    print(f"Период агрегатов: {date_from} — {max_date}")

    # Как в шаблоне — только offer_id и cost_price (или больше полей — смотрим заголовок)
    # Пишем ровно тот же формат, что и шаблон
    written = 0
    with open(OUT_MAIN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        for r in rows:
            # Заполняем только те поля, что есть в заголовке шаблона
            row_dict = {
                "offer_id": r["offer_id"] or "",
                "cost_price": r["cost_price"] if r["cost_price"] is not None else "",
            }
            # Дополнительные поля — на случай, если шаблон шире
            for col in header:
                if col not in row_dict:
                    row_dict[col] = ""
            w.writerow([row_dict.get(col, "") for col in header])
            written += 1

    print(f"\nЗаписано в {OUT_MAIN}: {written} строк")

    # Справочный файл — чтобы приоритизировать
    with open(OUT_INFO, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([
            "offer_id", "name", "category_l3", "brand",
            "cost_price_now",
            "revenue_30d", "orders_30d", "views_30d", "last_price",
            "priority"
        ])
        for i, r in enumerate(rows, 1):
            if r["revenue_30d"] > 0:
                priority = "1_PRODAETSYA"
            elif r["views_30d"] > 0:
                priority = "2_EST_POKAZY"
            else:
                priority = "3_TIHIY"
            w.writerow([
                r["offer_id"], r["name"], r["category_l3"], r["brand"],
                r["cost_price"] if r["cost_price"] is not None else "",
                f"{r['revenue_30d']:.0f}",
                r["orders_30d"],
                r["views_30d"],
                f"{r['last_price']:.0f}",
                priority,
            ])

    # Итоги по приоритетам
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
    print(f"  {OUT_MAIN}  — заполнить cost_price (отсортировано по важности)")
    print(f"  {OUT_INFO}  — справочная информация (сколько показов, продаж, цена)")

    con.close()


if __name__ == "__main__":
    main()
