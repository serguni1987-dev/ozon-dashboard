"""
sync_capital_logic.py — обновляет build_capital в sheets_sync.py:
1. Берёт баланс у Ozon из balance_history (API)
2. Убирает двойной счёт резерва закупок
3. Резерв штрафов = 3%
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# Найти блок "У Ozon к выплате" в build_capital
old = '''    # У Ozon к выплате (оценка)
    row = con.execute("""
        SELECT SUM(sale_price), SUM(sale_commission), SUM(bonus), SUM(coinvestment)
        FROM accruals
    """).fetchone()
    sale_sum = row[0] or 0
    comm_sum = row[1] or 0
    bonus_sum = row[2] or 0
    coinv_sum = row[3] or 0
    serv_sum = con.execute("SELECT SUM(amount) FROM accruals_services").fetchone()[0] or 0
    payouts_total = con.execute("SELECT SUM(amount) FROM payouts WHERE status = 'received'").fetchone()[0] or 0

    owed_by_ozon = sale_sum + comm_sum + bonus_sum + coinv_sum + serv_sum
    owed_by_ozon = max(0, owed_by_ozon - payouts_total)'''

new = '''    # У Ozon к выплате — ТОЧНО из balance_history
    bh = con.execute("""
        SELECT closing_balance FROM balance_history
        ORDER BY fetched_at DESC LIMIT 1
    """).fetchone()
    if bh:
        owed_by_ozon = bh[0] or 0
    else:
        owed_by_ozon = 0'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_capital: баланс из balance_history")
else:
    print("[?] Не нашёл блок 'У Ozon к выплате' в build_capital")

# Найти блок "ЧТО ЗАБРАТЬ" — исправить логику
old2 = '''    # === ЧТО ЗАБРАТЬ ===
    reserve_proc = revenue_30 * 0.10
    reserve_fines = revenue_30 * 0.05
    free_money = on_account + owed_by_ozon - tax_reserve - reserve_proc - reserve_fines'''

new2 = '''    # === ЧТО ЗАБРАТЬ ===
    # Резерв закупок = план из procurement_plan (будущие платежи)
    today_str = datetime.now().strftime("%Y-%m-%d")
    reserve_proc = con.execute("""
        SELECT SUM(amount) FROM procurement_plan
        WHERE status = 'planned' AND due_date >= ?
    """, (today_str,)).fetchone()[0] or 0

    # Резерв штрафов = 3% от выручки
    reserve_fines = revenue_30 * 0.03

    free_money = on_account + owed_by_ozon - tax_reserve - reserve_proc - reserve_fines'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] build_capital: логика резервов исправлена")
else:
    print("[?] Не нашёл блок ЧТО ЗАБРАТЬ")

# В build_capital — заголовок "У Ozon к выплате" переименуем в "точно из API"
src = src.replace(
    '''data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", f"{owed_by_ozon/total_assets*100 if total_assets else 0:.1f}%",
                 "оценка по начислениям", ""])''',
    '''data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", f"{owed_by_ozon/total_assets*100 if total_assets else 0:.1f}%",
                 "точно из API", ""])'''
)
print("[OK] Подпись 'точно из API'")

# В блоке ЧТО ЗАБРАТЬ — обновим подписи
src = src.replace(
    '''data.append(["Резерв закупок (10%)", f"-{reserve_proc:,.0f}", "",
                 "чтобы не остаться без товара", ""])''',
    '''if reserve_proc > 0:
        data.append(["План закупок", f"-{reserve_proc:,.0f}", "",
                     "из листа ВВОД", ""])
    else:
        data.append(["План закупок", "0", "",
                     "нет плана", ""])'''
)
print("[OK] Подпись 'План закупок'")

src = src.replace(
    '''data.append(["Резерв штрафов (5%)", f"-{reserve_fines:,.0f}", "",
                 "на риски и ошибки", ""])''',
    '''data.append(["Резерв штрафов (3%)", f"-{reserve_fines:,.0f}", "",
                 "на риски и ошибки", ""])'''
)
print("[OK] Подпись '3%'")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
