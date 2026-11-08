import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row
print("=== postings_daily по месяцам ===")
for r in con.execute("""
    SELECT substr(date,1,7) AS m,
           COUNT(*) AS n,
           SUM(quantity) AS qty,
           SUM(CASE WHEN is_cancelled=1 THEN quantity ELSE 0 END) AS canc,
           SUM(CASE WHEN is_returned=1 THEN quantity ELSE 0 END) AS ret
    FROM postings_daily
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}: строк={r['n']}, шт={r['qty']}, отмен={r['canc']}, возвратов={r['ret']}")

print("\n=== realization_daily по месяцам ===")
for r in con.execute("""
    SELECT substr(date,1,7) AS m,
           COUNT(*) AS n,
           SUM(CASE WHEN seller_price>0 THEN quantity ELSE 0 END)
         - SUM(CASE WHEN seller_price<0 THEN quantity ELSE 0 END) AS bought,
           ROUND(SUM(sale_price), 2) AS sale,
           ROUND(SUM(commission), 2) AS comm
    FROM realization_daily
    GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}: строк={r['n']}, выкуплено={r['bought']}, "
          f"sale_price={r['sale']}, commission={r['comm']}")