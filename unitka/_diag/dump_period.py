import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row
print("=== Все строки с seller_price > 0 и commission < 0 за 01.09-03.10 ===")
for r in con.execute("""
    SELECT date, sku, posting_number, quantity, seller_price, sale_price, bonus, coinvestment, commission
    FROM realization_daily
    WHERE date BETWEEN ? AND ? AND seller_price > 0 AND commission < 0
    ORDER BY date, sku
""", ("2026-09-01","2026-10-03")):
    print(f"{r['date']}  sku={r['sku']:>12}  posting={r['posting_number']:<22}  q={r['quantity']}  sp={r['seller_price']:>9.2f}  slp={r['sale_price']:>9.2f}  b={r['bonus']:>9.2f}  ci={r['coinvestment']:>7.2f}  comm={r['commission']:>10.2f}")
con.close()
