import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("=== posting_number для SKU 1605108599 в postings_daily ===")
for r in con.execute("""
    SELECT posting_number, date, status, is_cancelled, is_returned, quantity
    FROM postings_daily
    WHERE sku = '1605108599'
    ORDER BY date
"""):
    print(f"  {r['posting_number']} | {r['date']} | {r['status']} | "
          f"cancel={r['is_cancelled']} ret={r['is_returned']} qty={r['quantity']}")

print("\n=== posting_number для SKU 1605108599 в realization_daily ===")
for r in con.execute("""
    SELECT DISTINCT posting_number, date, seller_price, commission
    FROM realization_daily
    WHERE sku = 1605108599 AND date BETWEEN '2026-09-01' AND '2026-09-30'
    ORDER BY date
"""):
    print(f"  {r['posting_number']} | {r['date']} | seller={r['seller_price']} | comm={r['commission']}")