import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row
START, END = "2026-09-01", "2026-10-03"

print("=== postings_daily ===")
for r in con.execute("""
    SELECT COUNT(*) AS n,
           SUM(quantity) AS qty,
           SUM(CASE WHEN is_cancelled=1 THEN quantity ELSE 0 END) AS canc,
           SUM(CASE WHEN is_returned=1  THEN quantity ELSE 0 END) AS ret
    FROM postings_daily
    WHERE date BETWEEN ? AND ?
""", (START, END)):
    print(f"  строк={r['n']}, всего шт={r['qty']}, "
          f"отмен={r['canc']}, возвратов={r['ret']}")
    print(f"  выкупы (qty-canc-ret) = {r['qty'] - r['canc'] - r['ret']}")

print("\n=== realization_daily (начисления) ===")
for r in con.execute("""
    SELECT COUNT(*) AS n,
           SUM(CASE WHEN seller_price>0 THEN quantity ELSE 0 END)
         - SUM(CASE WHEN seller_price<0 THEN quantity ELSE 0 END) AS bought
    FROM realization_daily
    WHERE date BETWEEN ? AND ?
""", (START, END)):
    print(f"  строк={r['n']}, выкуплено (seller_price>0) = {r['bought']}")

print("\n=== Эталон Ozon ===")
print("  выкупы 21, отмены 38")