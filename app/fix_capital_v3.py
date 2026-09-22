"""
fix_capital_v3.py — 3 фикса листа КАПИТАЛ:
1. Разделить «На счету» и «У Ozon» в блоке 2
2. Блок 3 ПРОГНОЗ — реальные недели из payouts
3. Заголовок «У Ozon» = «точный баланс»
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Разделить "На счету" и "У Ozon" в build_capital ===
old1 = '''data.append(["На счету + у Ozon", f"{on_account + owed_by_ozon:,.0f}", "",
                 "что можно получить", ""])'''

new1 = '''data.append(["На счету (в руках)", f"{on_account:,.0f}", "",
                 "уже доступно", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", "",
                 "придёт в ближайшие дни", ""])'''

if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] Разделили 'На счету' и 'У Ozon'")
else:
    print("[?] Не нашёл строку в build_capital")

# === 2. Блок 3 ПРОГНОЗ — из payouts ===
old2 = '''    # === ПРОГНОЗ 14 ДНЕЙ ===
    today = datetime.now()
    payments = con.execute("""
        SELECT due_date, supplier, amount FROM procurement_plan
        WHERE status = 'planned' AND due_date BETWEEN ? AND ?
        ORDER BY due_date ASC
    """, (today.strftime("%Y-%m-%d"),
          (today + timedelta(days=14)).strftime("%Y-%m-%d"))).fetchall()

    # Приходы: 2 недели
    weekly_inflow = owed_by_ozon / 4 if owed_by_ozon else 0'''

new2 = '''    # === ПРОГНОЗ 14 ДНЕЙ ===
    today = datetime.now()

    # Реальные выплаты из payouts (ожидаемые)
    expected_payouts = con.execute("""
        SELECT period_begin, period_end, total_amount
        FROM payouts WHERE status = 'expected'
        ORDER BY period_begin DESC LIMIT 5
    """).fetchall()

    # План закупок
    payments = con.execute("""
        SELECT due_date, supplier, amount FROM procurement_plan
        WHERE status = 'planned' AND due_date BETWEEN ? AND ?
        ORDER BY due_date ASC
    """, (today.strftime("%Y-%m-%d"),
          (today + timedelta(days=14)).strftime("%Y-%m-%d"))).fetchall()'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] fetch_payouts подключён в прогноз")

# === 3. В data — реальные недели ===
old3 = '''    data.append(["3. КАССОВЫЙ ПРОГНОЗ (14 дней)", "", "", "", ""])
    data.append(["Что", "Когда", "Сумма руб", "", ""])
    data.append(["Приход от Ozon, неделя 1", "ожидается", "+" + f"{weekly_inflow:,.0f}",
                 "оценка", ""])
    data.append(["Приход от Ozon, неделя 2", "ожидается", "+" + f"{weekly_inflow:,.0f}",
                 "оценка", ""])
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])
    else:
        data.append(["Платежи поставщикам", "нет плана", "0", "", ""])
    data.append(["Налог УСН (аванс)", "раз в квартал", "-" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])'''

new3 = '''    data.append(["3. КАССОВЫЙ ПРОГНОЗ (14 дней)", "", "", "", ""])
    data.append(["Что", "Когда", "Сумма руб", "", ""])

    # Приходы от Ozon — реальные недели
    if expected_payouts:
        for i, (pb, pe, amt) in enumerate(expected_payouts[:2], 1):
            data.append([f"Приход от Ozon (неделя {i})",
                         f"{pb[5:]} - {pe[5:]}",
                         f"+{amt:,.0f}",
                         "из API", ""])
    else:
        data.append(["Приход от Ozon", "нет данных", "0", "запусти fetch_payouts.py", ""])

    # План закупок
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])
    else:
        data.append(["Платежи поставщикам", "нет плана", "0", "", ""])

    data.append(["Налог УСН (аванс)", "раз в квартал", "-" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])'''

if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Блок 3 — реальные недели")
else:
    print("[?] Не нашёл блок 3 в build_capital")

# === 4. Обновляем format_capital: сдвиг строк ===
# Было: 15 заголовок, 16-19 данные (4), 20 МОЖНО ЗАБРАТЬ
# Стало: 15 заголовок, 16-20 данные (5), 21 МОЖНО ЗАБРАТЬ

old_fmt2 = '''    ops.append({"type": "format", "range": "A15:E15", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(16, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    ops.append({"type": "format", "range": "A20", "format": free_fmt})
    ops.append({"type": "format", "range": "B20:C20", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 20, "height": 34})'''

new_fmt2 = '''    ops.append({"type": "format", "range": "A15:E15", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(16, 21):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    ops.append({"type": "format", "range": "A21", "format": free_fmt})
    ops.append({"type": "format", "range": "B21:C21", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 21, "height": 34})'''

if old_fmt2 in src:
    src = src.replace(old_fmt2, new_fmt2)
    print("[OK] format_capital: блок 2 теперь 5 строк данных")

# === 5. Сдвигаем блоки 3, 4, 5 на 1 строку ===
src = src.replace('"range": "A22:E22"', '"range": "A23:E23"')
src = src.replace('"range": "A23:E23", "format": tbl_hdr', '"range": "A24:E24", "format": tbl_hdr')
src = src.replace('for r in range(24, 29):', 'for r in range(25, 30):')
src = src.replace('"range": "A30:E30"', '"range": "A31:E31"')
src = src.replace('"range": "A31:E31", "format": tbl_hdr', '"range": "A32:E32", "format": tbl_hdr')
src = src.replace('for r in range(32, 36):', 'for r in range(33, 37):')
src = src.replace('"range": "A37:E37"', '"range": "A38:E38"')
src = src.replace('for r in range(38, 45):', 'for r in range(39, 46):')
src = src.replace('vals = ws.get("A38:A44")', 'vals = ws.get("A39:A45")')
src = src.replace('r = 38 + i', 'r = 39 + i')
print("[OK] format_capital: блоки сдвинуты на 1 строку")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
