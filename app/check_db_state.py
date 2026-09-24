import sqlite3, os
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("ТАБЛИЦЫ:")
for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    n = con.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0]
    print(f"  {r[0]:<35} {n:>8}")

print()
print("REALIZATION по месяцам:")
for r in con.execute("""
    SELECT month, COUNT(*) AS n, SUM(quantity) AS qty, SUM(sale_price) AS slp
    FROM monthly_realization_rows GROUP BY month ORDER BY month
"""):
    print(f"  {r['month']}  строк: {r['n']:>4}  qty: {r['qty'] or 0:>5}  slp: {r['slp'] or 0:>14,.2f}")

print()
print("ACCRUALS по месяцам:")
for r in con.execute("""
    SELECT substr(date,1,7) AS m, COUNT(*) AS n
    FROM accruals GROUP BY m ORDER BY m
"""):
    print(f"  {r['m']}  записей: {r['n']:>5}")

print()
print("Продукты с себестоимостью:")
r = con.execute("""
    SELECT COUNT(*) AS total,
           SUM(CASE WHEN cost_price > 0 THEN 1 ELSE 0 END) AS with_cost
    FROM products WHERE is_own = 1
""").fetchone()
print(f"  Всего: {r['total']}, с себестоимостью: {r['with_cost']}")

con.close()
