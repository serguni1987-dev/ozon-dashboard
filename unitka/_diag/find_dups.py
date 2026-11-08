import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
D1, D2 = "2026-09-01", "2026-10-03"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== 1) Дубли по posting_number + sku (разные accrual_id) ===")
rows = con.execute("""
    SELECT posting_number, sku, COUNT(*) AS n,
           GROUP_CONCAT(accrual_id) AS accs,
           SUM(seller_price) AS sp_sum, SUM(quantity) AS q_sum
    FROM realization_daily
    WHERE date BETWEEN ? AND ? AND seller_price > 0 AND commission < 0
    GROUP BY posting_number, sku HAVING COUNT(*) > 1
    ORDER BY sp_sum DESC
""", (D1, D2)).fetchall()
print("Найдено:", len(rows))
for r in rows[:20]:
    print(" posting=" + str(r["posting_number"]) + " sku=" + str(r["sku"]) + " n=" + str(r["n"]) + " accs=" + str(r["accs"]) + " sp_sum=" + str(r["sp_sum"]))

print()
print("=== 2) Строки с seller_price>0 и commission>=0 ===")
total = con.execute("""
    SELECT COUNT(*) AS n, SUM(seller_price) AS sp, SUM(sale_price) AS slp
    FROM realization_daily
    WHERE date BETWEEN ? AND ? AND seller_price > 0 AND commission >= 0
""", (D1, D2)).fetchone()
print("ВСЕГО:", total["n"], "строк, sp =", total["sp"], ", slp =", total["slp"])
for r in con.execute("""
    SELECT date, sku, posting_number, quantity, seller_price, sale_price, commission
    FROM realization_daily
    WHERE date BETWEEN ? AND ? AND seller_price > 0 AND commission >= 0
    ORDER BY date, sku LIMIT 20
""", (D1, D2)):
    print(" " + r["date"] + " sku=" + str(r["sku"]) + " posting=" + str(r["posting_number"]) + " q=" + str(r["quantity"]) + " sp=" + str(r["seller_price"]) + " slp=" + str(r["sale_price"]) + " comm=" + str(r["commission"]))

print()
print("=== 3) Заказы, выкупы, отмены ===")
r = con.execute("""
    SELECT COUNT(*) AS n,
           SUM(CASE WHEN seller_price > 0 THEN quantity ELSE 0 END) AS q_pos,
           SUM(CASE WHEN seller_price < 0 THEN quantity ELSE 0 END) AS q_neg,
           SUM(CASE WHEN seller_price > 0 AND commission < 0 THEN 1 ELSE 0 END) AS rows_normal,
           SUM(CASE WHEN seller_price > 0 AND commission >= 0 THEN 1 ELSE 0 END) AS rows_weird
    FROM realization_daily WHERE date BETWEEN ? AND ?
""", (D1, D2)).fetchone()
print("всего строк:", r["n"])
print("q_pos (seller>0):", r["q_pos"])
print("q_neg (seller<0):", r["q_neg"])
print("нормальных строк (seller>0, comm<0):", r["rows_normal"])
print("странных строк (seller>0, comm>=0):", r["rows_weird"])

con.close()
