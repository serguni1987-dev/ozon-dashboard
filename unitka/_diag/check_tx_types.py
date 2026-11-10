import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== Уникальные значения поля 'type' в finance_transactions ===")
cur.execute("SELECT type, COUNT(*), SUM(amount) FROM finance_transactions GROUP BY type ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print(f"  type = {repr(row[0]):20} | строк: {row[1]:>5} | сумма: {row[2]:>15,.2f}")

print("\n=== Октябрь 2026: детально по типам ===")
cur.execute("""
    SELECT type, COUNT(*), SUM(amount) 
    FROM finance_transactions 
    WHERE substr(date,1,7) = '2026-10'
    GROUP BY type
""")
for row in cur.fetchall():
    print(f"  type = {repr(row[0]):20} | строк: {row[1]:>5} | сумма: {row[2]:>15,.2f}")

print("\n=== Проверка: sum(amount) за октябрь ===")
cur.execute("SELECT SUM(amount) FROM finance_transactions WHERE substr(date,1,7) = '2026-10'")
print(f"  SUM(amount) = {cur.fetchone()[0]:,.2f}")
con.close()