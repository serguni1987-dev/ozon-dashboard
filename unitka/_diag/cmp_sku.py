import sqlite3, io, csv
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

# 1. Наши суммы за сентябрь по SKU
ours = {}
for r in con.execute("""
    SELECT sku,
           ROUND(SUM(seller_price), 2) AS seller,
           ROUND(SUM(sale_price), 2)   AS sale,
           ROUND(SUM(sale_amount), 2)  AS sale_amt,
           ROUND(SUM(commission), 2)   AS comm,
           ROUND(SUM(bonus), 2)        AS bonus,
           ROUND(SUM(delivery_total), 2) AS delivery
    FROM realization_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-09-30'
    GROUP BY sku
"""):
    ours[int(r["sku"])] = dict(r)

# 2. Эталон — возьмём из файла (вставим вручную топ по сумме)
# SKU: (заказы, выкупы, отмены, отмены_руб, выручка, комиссия, логистика)
etalon = {
    2287077409: (4, 3, 1, 10246, 30738, 15778.84, 1219.59),
    1566289468: (7, 5, 2, 7358.4, 18396, 9198, 553.06),
    4257934481: (1, 1, 0, 0, 8393, 4364.35, 235.9),
    1605108599: (8, 0, 8, 0, 11802, 6137.04, 1596.4),
    2287080727: (4, 1, 3, 30438, 10146, 5275.92, 778.09),
    1288892888: (1, 1, 0, 0, 31947, 15973.5, 540.3),
    4257934218: (1, 1, 0, 0, 24421, 12210.5, 173.35),
    1288893361: (4, 1, 3, 42768, 14256, 7128, 1074.41),
    2022731281: (1, 1, 0, 0, 7249, 3624.5, 829.6),
}

print(f"{'SKU':>12} | {'эт.Выручка':>10} {'наш.seller':>11} | {'эт.Комиссия':>11} {'наш.comm':>10} | {'эт.Логист':>9} {'наш.deliv':>10}")
for sku, (ord_, purch, canc, canc_rub, rev, comm, log) in etalon.items():
    o = ours.get(sku, {})
    print(f"{sku:>12} | {rev:>10} {o.get('seller', 0):>11} | "
          f"{comm:>11} {abs(o.get('comm', 0)):>10} | "
          f"{log:>9} {abs(o.get('delivery', 0)):>10}")