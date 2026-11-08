import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("=== realization_daily за сентябрь по статусу postings ===")
print(f"{'статус':<20} {'n':>5} {'seller':>12} {'sale':>12} {'sale_amt':>12} {'comm':>12} {'bonus':>12}")
for r in con.execute("""
    SELECT COALESCE(p.status, '(no match)') AS st,
           COUNT(*) AS n,
           ROUND(SUM(r.seller_price), 2) AS sp,
           ROUND(SUM(r.sale_price), 2)   AS slp,
           ROUND(SUM(r.sale_amount), 2)  AS sla,
           ROUND(SUM(r.commission), 2)   AS cm,
           ROUND(SUM(r.bonus), 2)        AS b
    FROM realization_daily r
    LEFT JOIN postings_daily p ON p.posting_number = r.posting_number
    WHERE r.date BETWEEN '2026-09-01' AND '2026-09-30'
      AND (r.seller_price != 0 OR r.commission != 0)
    GROUP BY st ORDER BY ABS(SUM(r.seller_price)) DESC
"""):
    print(f"{r['st']:<20} {r['n']:>5} {r['sp']:>12} {r['slp']:>12} "
          f"{r['sla']:>12} {r['cm']:>12} {r['b']:>12}")

print("\n=== Только выкупленные (delivered) ===")
for r in con.execute("""
    SELECT COUNT(*) AS n,
           ROUND(SUM(r.seller_price), 2) AS sp,
           ROUND(SUM(r.sale_price), 2)   AS slp,
           ROUND(SUM(r.sale_amount), 2)  AS sla,
           ROUND(SUM(r.commission), 2)   AS cm,
           ROUND(SUM(r.bonus), 2)        AS b,
           ROUND(SUM(r.coinvestment), 2) AS ci,
           ROUND(SUM(r.delivery_total), 2) AS dl
    FROM realization_daily r
    JOIN postings_daily p ON p.posting_number = r.posting_number
    WHERE r.date BETWEEN '2026-09-01' AND '2026-09-30'
      AND p.status = 'delivered'
"""):
    print(f"  строк={r['n']}")
    print(f"  seller_price = {r['sp']}  (эталон Выручка: 238113)")
    print(f"  sale_price   = {r['slp']}")
    print(f"  sale_amount  = {r['sla']}")
    print(f"  commission   = {r['cm']}  (эталон Комиссия: 121002)")
    print(f"  bonus        = {r['b']}")
    print(f"  coinvestment = {r['ci']}")
    print(f"  delivery_total = {r['dl']}  (эталон Логистика: 13890)")