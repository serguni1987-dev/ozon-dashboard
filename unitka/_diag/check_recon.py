import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== ДАННЫЕ ДЛЯ СВЕРКИ (по месяцам) ===")
print(f"{'Месяц':<10} | {'Начислено':>15} | {'Удержано':>15} | {'К выплате':>15}")
print("-" * 65)

cur.execute("""
    SELECT 
        substr(date, 1, 7) AS month,
        SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS accrued,
        SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) AS withheld,
        SUM(amount) AS net
    FROM finance_transactions
    GROUP BY substr(date, 1, 7)
    ORDER BY month
""")
for r in cur.fetchall():
    print(f"{r['month']:<10} | {r['accrued']:>15,.2f} | {r['withheld']:>15,.2f} | {r['net']:>15,.2f}")

print("\n=== ВЫПЛАТЫ ===")
cur.execute("""
    SELECT substr(date, 1, 7) AS month, SUM(amount) AS paid, COUNT(*) AS cnt
    FROM finance_payouts
    GROUP BY substr(date, 1, 7)
    ORDER BY month
""")
for r in cur.fetchall():
    print(f"{r['month']:<10} | Выплачено: {r['paid']:>15,.2f} | операций: {r['cnt']}")
con.close()