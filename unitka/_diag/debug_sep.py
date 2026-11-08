import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("=== realization_daily за сентябрь ===")
for r in con.execute("""
    SELECT COUNT(*) AS n,
           ROUND(SUM(seller_price), 2)   AS seller_price,
           ROUND(SUM(sale_price), 2)     AS sale_price,
           ROUND(SUM(commission), 2)     AS commission,
           ROUND(SUM(bonus), 2)          AS bonus,
           ROUND(SUM(coinvestment), 2)   AS coinvestment,
           ROUND(SUM(delivery_total), 2) AS delivery_total
    FROM realization_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-09-30'
"""):
    for k in r.keys(): print(f"  {k}: {r[k]}")

print("\n=== Топ-10 типов начислений с SKU за сентябрь ===")
for r in con.execute("""
    SELECT a.type_id, t.name, COUNT(*) AS n, ROUND(SUM(a.amount),2) AS total
    FROM accrual_sku_daily a
    LEFT JOIN accrual_types t ON t.id = a.type_id
    WHERE a.date BETWEEN '2026-09-01' AND '2026-09-30'
    GROUP BY a.type_id ORDER BY ABS(SUM(a.amount)) DESC LIMIT 10
"""):
    print(f"  id={r['type_id']:>4} {r['name']!r}: n={r['n']} sum={r['total']}")

print("\n=== Эталон ===")
print("  Выручка:     238113")
print("  Комиссия МП: 121001.96")