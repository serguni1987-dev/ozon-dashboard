import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

for month_label, d1, d2 in [("АВГУСТ", "2026-08-01", "2026-08-31"), ("СЕНТЯБРЬ", "2026-09-01", "2026-09-19")]:
    print(f"\n=== {month_label} — ТОП-5 по выручке ===")
    rows = con.execute("""
        SELECT p.offer_id, p.name, p.cost_price,
               SUM(sd.revenue) AS rev, SUM(sd.orders_units) AS orders,
               AVG(sd.avg_price) AS avg_price
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
        ORDER BY rev DESC LIMIT 5
    """, (d1, d2)).fetchall()
    for r in rows:
        cost = (r["cost_price"] or 0) * r["orders"]
        profit = r["rev"] * 0.83 - cost  # примерная маржа
        name = (r["name"] or "")[:45]
        print(f"  {r['offer_id']:<18} {name:<45} выручка {r['rev']:>9,.0f} ₽, "
              f"зак {r['orders']}, ср.цена {r['avg_price']:>7,.0f}, себест {r['cost_price']:>6,.0f}")

con.close()
