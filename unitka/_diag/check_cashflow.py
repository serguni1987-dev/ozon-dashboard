import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== finance_payouts (выплаты) ===")
cur.execute("SELECT COUNT(*), SUM(amount), MIN(date), MAX(date) FROM finance_payouts")
r = cur.fetchone()
print(f"  Строк: {r[0]} | Всего выплат: {r[1]:,.2f} ₽ | С {r[2]} по {r[3]}")

print("\n=== finance_transactions (транзакции) ===")
cur.execute("SELECT COUNT(*), SUM(amount) FROM finance_transactions")
r = cur.fetchone()
print(f"  Строк: {r[0]} | Итого: {r[1]:,.2f} ₽")

print("\n=== Проверка: сколько выплат за октябрь ===")
cur.execute("SELECT SUM(amount) FROM finance_payouts WHERE substr(date,1,7) = '2026-10'")
print(f"  Октябрь: {cur.fetchone()[0]:,.2f} ₽")

print("\n=== Проверка: сколько расходов в ДДС (по коду) ===")
# Смотрим, что calc_cashflow может брать за расходы
cur.execute("SELECT DISTINCT type FROM finance_transactions")
print("  Типы транзакций:", [r[0] for r in cur.fetchall()])
con.close()