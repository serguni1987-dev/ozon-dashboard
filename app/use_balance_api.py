"""
use_balance_api.py — calc_capital теперь берёт баланс из balance_history.
"""
import re
src = open("calc_capital.py", encoding="utf-8").read()

# 1. Заменяем блок "У Ozon к выплате" — берём из balance_history
old = '''    # 1.2. У Ozon к выплате — из accruals минус выплаты
    #    (в базе accruals total_amount — это начисления; нужно понять, что уже выплачено)
    accruals_total = con.execute("""
        SELECT SUM(total_amount) FROM accruals
    """).fetchone()[0] or 0

    payouts_total = con.execute("""
        SELECT SUM(amount) FROM payouts WHERE status = 'received'
    """).fetchone()[0] or 0

    # Простая логика: то, что Ozon ещё должен = начисления - выплаты
    # Но у accruals отрицательные суммы (это удержания), положительные — компенсации
    # Проверим реальную структуру
    pos = con.execute("SELECT SUM(total_amount) FROM accruals WHERE total_amount > 0").fetchone()[0] or 0
    neg = con.execute("SELECT SUM(total_amount) FROM accruals WHERE total_amount < 0").fetchone()[0] or 0

    # Что реально осталось у Ozon = положительные - отрицательные (абс)
    # Более честно: выручка (sale_price) минус всё удержанное
    sale_sum = con.execute("SELECT SUM(sale_price) FROM accruals").fetchone()[0] or 0
    comm_sum = con.execute("SELECT SUM(sale_commission) FROM accruals").fetchone()[0] or 0
    bonus_sum = con.execute("SELECT SUM(bonus) FROM accruals").fetchone()[0] or 0
    coinv_sum = con.execute("SELECT SUM(coinvestment) FROM accruals").fetchone()[0] or 0
    serv_sum = con.execute("SELECT SUM(amount) FROM accruals_services").fetchone()[0] or 0

    # То, что Ozon должен продавцу (приблизительно):
    # sale_price (что заплатил покупатель) 
    # минус комиссия + bonus + coinvestment (компенсация)
    # минус услуги (логистика и т.д.)
    owed_by_ozon = sale_sum + comm_sum + bonus_sum + coinv_sum + serv_sum
    owed_by_ozon = max(0, owed_by_ozon - payouts_total)

    print(f"  У Ozon к выплате:       {money(owed_by_ozon)}")
    print(f"    (начисления: {money(sale_sum)}, удержания: {money(comm_sum + serv_sum)}, "
          f"компенсации: {money(bonus_sum + coinv_sum)})")'''

new = '''    # 1.2. У Ozon к выплате — ТОЧНО из balance_history (API)
    bh = con.execute("""
        SELECT fetched_at, closing_balance, accrued, payments, date_from, date_to
        FROM balance_history
        ORDER BY fetched_at DESC LIMIT 1
    """).fetchone()

    if bh:
        owed_by_ozon = bh[1] or 0
        bh_fetched = bh[0]
        bh_accrued = bh[2] or 0
        bh_payments = bh[3] or 0
        bh_from = bh[4]
        bh_to = bh[5]
        print(f"  У Ozon к выплате:       {money(owed_by_ozon)}")
        print(f"    (точно из API, обновлено {bh_fetched[:16]})")
        print(f"    период: {bh_from} — {bh_to}")
        print(f"    начислено: {money(bh_accrued)}, выплачено: {money(bh_payments)}")
    else:
        owed_by_ozon = 0
        print(f"  У Ozon к выплате:       {money(0)}  (запусти py fetch_balance.py)")'''

if old in src:
    src = src.replace(old, new)
    print("[OK] calc_capital: берёт баланс из balance_history")
else:
    print("[?] Не нашёл блок расчёта у Ozon")

open("calc_capital.py", "w", encoding="utf-8").write(src)
print("Готово.")
