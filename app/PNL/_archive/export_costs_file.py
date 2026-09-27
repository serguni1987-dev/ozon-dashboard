"""
export_costs_file.py - v4: без колонок Выручка и Заказов.
"""
import csv
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
ROOT = os.path.dirname(APP_DIR)
OUT_DIR = os.path.join(ROOT, "Себестоимость")
OUT_CSV = os.path.join(OUT_DIR, "costs_all.csv")

os.makedirs(OUT_DIR, exist_ok=True)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Сортировка по категории, потом по артикулу (без выручки)
rows = con.execute("""
    SELECT p.sku, p.offer_id, p.name, p.category_l2,
           p.cost_price, p.cost_date
    FROM products p
    WHERE p.is_own = 1
    ORDER BY p.category_l2, p.offer_id
""").fetchall()

print("Всего своих SKU:", len(rows))

filled = 0
empty = 0

HEADERS = [
    "Артикул",
    "SKU",
    "Название",
    "Категория",
    "Себестоимость",
    "Дата себестоимости",
    "Комментарий",
]

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(HEADERS)
    for r in rows:
        cost = r["cost_price"]
        if cost and cost > 0:
            filled += 1
            cost_val = f"{cost:.2f}"
        else:
            empty += 1
            cost_val = ""
        w.writerow([
            r["offer_id"] or "",
            r["sku"],
            r["name"] or "",
            r["category_l2"] or "",
            cost_val,
            r["cost_date"] or "",
            "",
        ])

print()
print("[OK] Файл:", OUT_CSV)
print("    Всего строк:", len(rows))
print("    С себестоимостью:", filled)
print("    Без себестоимости:", empty)
size = os.path.getsize(OUT_CSV) / 1024
print("    Размер:", round(size, 1), "КБ")
print()
print("Заголовки:", " | ".join(HEADERS))

con.close()
