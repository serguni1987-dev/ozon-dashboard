"""
export_costs_template.py
Экспортирует активные SKU (у которых были продажи) в CSV-шаблон.
Ты заполнишь колонку cost_price и запустишь import_costs.py.
"""
import sqlite3
import csv
import os

DB_PATH = "ozon.db"
OUT_FILE = "costs_template.csv"


def main():
    conn = sqlite3.connect(DB_PATH)

    # Активные SKU = у которых была выручка > 0
    cur = conn.execute("""
        SELECT
            p.offer_id,
            p.sku,
            p.name,
            p.category_l2,
            ROUND(SUM(s.revenue), 0)   AS revenue_period,
            SUM(s.orders_units)         AS orders_period
        FROM sales_daily s
        JOIN products p ON p.sku = s.sku
        WHERE p.is_own = 1
        GROUP BY s.sku
        HAVING SUM(s.revenue) > 0
        ORDER BY revenue_period DESC
    """)
    rows = cur.fetchall()

    with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        # Шапка
        w.writerow([
            "offer_id", "sku", "name", "category_l2",
            "revenue_period", "orders_period",
            "cost_price",           # ← это заполнишь ты
            "comment"               # ← сюда можно записать заметку
        ])
        for r in rows:
            w.writerow([*r, "", ""])

    conn.close()

    print(f"[OK] Шаблон сохранён: {OUT_FILE}")
    print(f"[OK] SKU для заполнения: {len(rows)}")
    print()
    print("Что делать:")
    print(f"  1. Открой {OUT_FILE} в Excel (двойной клик)")
    print(f"  2. Заполни колонку cost_price (себестоимость в рублях)")
    print(f"  3. Сохрани файл (Ctrl+S)")
    print(f"  4. Запусти: py import_costs.py")


if __name__ == "__main__":
    main()