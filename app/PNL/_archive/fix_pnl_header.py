"""
fix_pnl_header.py - 2 правки:
1. Заголовки месяцев — в строку 2 (не в 1).
2. Для месяцев без realization — fallback на accruals.
"""
src = open("sync_pnl.py", encoding="utf-8").read()

# === Правка 1: заголовки в строку 2 ===
old = '''    rows = []
    header = [""] * 19
    header[0] = "Отчёт о прибылях и убытках OZON"
    header[1] = f"Всего за {year}"
    for i, name in enumerate(MONTHS):
        header[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        header[qcol(i + 1) - 1] = name
    rows.append(header)
    rows.append([""] * 19)'''

new = '''    rows = []
    # Строка 1 — только название (объединяется)
    rows.append(["Отчёт о прибылях и убытках OZON"] + [""] * 18)

    # Строка 2 — заголовки колонок
    row2 = [""] * 19
    row2[0] = ""
    row2[1] = f"Всего за {year}"
    for i, name in enumerate(MONTHS):
        row2[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        row2[qcol(i + 1) - 1] = name
    rows.append(row2)'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Заголовки месяцев перенесены в строку 2")
else:
    print("[?] Не нашёл блок заголовков")

# === Правка 2: fallback на accruals для месяцев без realization ===
old2 = '''    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    sale_price = f(r["slp"])
    bonus = f(r["bonus"])
    coinv = f(r["coinv"])
    commission = abs(f(r["comm"]))'''

new2 = '''    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    sale_price = f(r["slp"])
    bonus = f(r["bonus"])
    coinv = f(r["coinv"])
    commission = abs(f(r["comm"]))

    # Fallback: если realization за месяц ещё нет (или пусто) —
    # берём из accruals
    if sale_price == 0 and bonus == 0:
        r2 = con.execute("""
            SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
                   SUM(coinvestment) AS coinv, SUM(sale_commission) AS comm
            FROM accruals WHERE date >= ? AND date < ?
        """, (d1, d2)).fetchone()
        sale_price = f(r2["slp"])
        bonus = f(r2["bonus"])
        coinv = f(r2["coinv"])
        commission = abs(f(r2["comm"]))'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Fallback на accruals для месяцев без realization")
else:
    print("[?] Не нашёл блок запроса realization")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("Готово.")
