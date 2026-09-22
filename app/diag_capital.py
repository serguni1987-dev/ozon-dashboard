"""
diag_capital.py — что уже есть в БД для блока КАПИТАЛ.
"""
import sqlite3

con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

print("=" * 80)
print("ЧТО ЕСТЬ В БД ДЛЯ КАПИТАЛА")
print("=" * 80)

# 1. accruals — начисления от Ozon
n = con.execute("SELECT COUNT(*) FROM accruals").fetchone()[0]
print(f"\n[1] accruals (начисления): {n}")
if n:
    r = con.execute("SELECT MIN(date), MAX(date) FROM accruals").fetchone()
    print(f"    Период: {r[0]} — {r[1]}")

    # Какие поля есть
    cols = [c[1] for c in con.execute("PRAGMA table_info(accruals)")]
    print(f"    Поля: {', '.join(cols)}")

# 2. current_stocks — текущие остатки
n = con.execute("SELECT COUNT(*) FROM current_stocks").fetchone()[0]
n_pos = con.execute("SELECT COUNT(*) FROM current_stocks WHERE total_present > 0").fetchone()[0]
print(f"\n[2] current_stocks: {n}, с остатком > 0: {n_pos}")

# 3. Заморожено в товаре
frozen = con.execute("""
    SELECT SUM(cs.total_present * p.cost_price)
    FROM current_stocks cs
    JOIN products p ON p.offer_id = cs.offer_id
    WHERE p.cost_price > 0
""").fetchone()[0] or 0
print(f"\n[3] В товаре на складе: {frozen:,.0f} ₽")

# 4. Услуги Ozon за всё время
serv = con.execute("SELECT SUM(amount) FROM accruals_services").fetchone()[0] or 0
print(f"\n[4] Услуги Ozon (всего начислено): {serv:,.0f} ₽")

# 5. Эффективная комиссия (баланс)
comm = con.execute("""
    SELECT SUM(sale_commission), SUM(bonus), SUM(coinvestment)
    FROM accruals
""").fetchone()
if comm:
    print(f"\n[5] Комиссии и компенсации:")
    print(f"    Гросс-комиссия: {comm[0]:,.0f} ₽")
    print(f"    Bonus:          {comm[1]:,.0f} ₽")
    print(f"    Coinvestment:   {comm[2]:,.0f} ₽")
    eff = (comm[0] or 0) + (comm[1] or 0) + (comm[2] or 0)
    print(f"    Эффективно:     {eff:,.0f} ₽")

# 6. Что нужно ДОБАВИТЬ
print("\n" + "=" * 80)
print("ЧТО НУЖНО ДОБАВИТЬ")
print("=" * 80)
print("""
[+] Таблица capital_input — ручной ввод:
    - on_account (₽) — сколько на счету сейчас
    - update_date — когда обновлено

[+] Таблица procurement_plan — план закупок:
    - supplier, amount, due_date, note

[+] Таблица payouts (или из accruals) — выплаты от Ozon:
    - date, amount, status

[?] transit_stock_count — в пути (из /v1/analytics/stocks или API)
""")

con.close()
