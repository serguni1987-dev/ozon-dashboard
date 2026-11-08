import sqlite3, json
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("=== No-match: начисления сентября без postings в сентябре ===")
total = 0
for r in con.execute("""
    SELECT r.date, r.posting_number, r.sku,
           r.seller_price, r.sale_price, r.commission,
           p.posting_number AS pn_match, p.date AS p_date, p.status
    FROM realization_daily r
    LEFT JOIN postings_daily p ON p.posting_number = r.posting_number
    WHERE r.date BETWEEN '2026-09-01' AND '2026-09-30'
      AND r.seller_price != 0
      AND p.posting_number IS NULL
    ORDER BY r.seller_price DESC
"""):
    total += r["seller_price"]
    print(f"  {r['date']} | {r['posting_number']} | sku={r['sku']} | "
          f"seller={r['seller_price']} | comm={r['commission']}")
print(f"  ИТОГО seller_price: {total}")

print("\n=== Проверим: есть ли эти posting_number за другие месяцы ===")
for r in con.execute("""
    SELECT DISTINCT r.posting_number
    FROM realization_daily r
    LEFT JOIN postings_daily p ON p.posting_number = r.posting_number
    WHERE r.date BETWEEN '2026-09-01' AND '2026-09-30'
      AND r.seller_price != 0
      AND p.posting_number IS NULL
"""):
    pn = r["posting_number"]
    other = con.execute("""
        SELECT date, status FROM postings_daily
        WHERE posting_number = ? LIMIT 1
    """, (pn,)).fetchone()
    if other:
        print(f"  {pn}: есть в postings_daily за {other['date']} ({other['status']})")
    else:
        print(f"  {pn}: нет вообще в postings_daily")