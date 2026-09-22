"""
fix_capital_layout.py — исправляет 3 бага в листах ВВОД и КАПИТАЛ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Прогноз: явные + и - ===
src = src.replace(
    '''data.append(["Приход от Ozon", "ожидается", "~" + f"{owed_by_ozon/4:,.0f}",
                 "оценка: /4 (раз в неделю)", ""])''',
    '''data.append(["Приход от Ozon", "ожидается", "+" + f"{owed_by_ozon/4:,.0f}",
                 "оценка: /4 (раз в неделю)", ""])'''
)

src = src.replace(
    '''data.append(["Налог УСН (аванс)", "раз в квартал", "~" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])''',
    '''data.append(["Налог УСН (аванс)", "раз в квартал", "-" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])'''
)

print("[OK] Прогноз: явные знаки + и -")

# === 2. Лист ВВОД: инструкция без пустой строки ===
old_input = '''    data.append(["", "", "", "", ""])
    data.append(["3. ИНСТРУКЦИЯ", "", "", "", ""])
    data.append(["Как заполнять", "", "", "", ""])
    data.append(["Остаток на счету", "ЛК Ozon → Финансы → Баланс, или ваш банк", "", "", ""])
    data.append(["План закупок", "Кому/сколько/когда платить поставщику", "", "", ""])
    data.append(["После ввода", "Запусти: py calc_capital_to_db.py (сохранит в БД)", "", "", ""])
    return data'''

new_input = '''    data.append(["", "", "", "", ""])
    data.append(["3. ИНСТРУКЦИЯ", "", "", "", ""])
    data.append(["Остаток на счету", "ЛК Ozon → Финансы → Баланс, или ваш банк", "", "", ""])
    data.append(["План закупок", "Кому/сколько/когда платить поставщику", "", "", ""])
    data.append(["После ввода", "Запусти: py calc_capital_to_db.py", "", "", ""])
    return data'''

if old_input in src:
    src = src.replace(old_input, new_input)
    print("[OK] ВВОД: инструкция сдвинута вверх")
else:
    print("[?] Не нашёл блок инструкции в build_input")

# === 3. Формат ВВОД: сдвиг строк инструкции 13-17 на 13-16 ===
old_fmt = '''    # 3. Инструкция
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(14, 18):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 28})'''

new_fmt = '''    # 3. Инструкция — строки 13-16
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(13, 17):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 28})'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] ВВОД: формат инструкции 13-16")
else:
    print("[?] Не нашёл блок форматирования инструкции")

# === 4. КАПИТАЛ: заголовки прогноза правильно на 21, данные 22+ ===
# В build_capital сейчас:
#   строка 20 = "3. КАССОВЫЙ ПРОГНОЗ"
#   строка 21 = заголовки (Что/Когда/Сумма)
#   строки 22+ = данные
# Всё верно. Проблема была только в знаках.

# === 5. КАПИТАЛ: форматирование блоков 3 и 4 ===
# Блок 3: 20 = заголовок, 21 = шапка таблицы, 22+ = данные
# Блок 4: 28 = заголовок, 29 = шапка таблицы, 30+ = данные
old_cap_fmt = '''    # Блок 3: ПРОГНОЗ
    ops.append({"type": "format", "range": "A21:E21", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 21, "height": 32})
    for r in range(22, 28):
        ops.append({"type": "row_height", "row": r, "height": 28})

    # Блок 4: ОБОРОТ
    ops.append({"type": "format", "range": "A28:E28", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 28, "height": 32})
    for r in range(29, 33):
        ops.append({"type": "row_height", "row": r, "height": 28})'''

new_cap_fmt = '''    # Блок 3: ПРОГНОЗ — заголовки на 21, данные 22-27
    ops.append({"type": "format", "range": "A21:E21", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 21, "height": 32})
    for r in range(22, 28):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=11), horizontalAlignment='CENTER', verticalAlignment='MIDDLE')})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # Блок 4: ОБОРОТ — заголовки на 29, данные 30-33
    ops.append({"type": "format", "range": "A29:E29", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 29, "height": 32})
    for r in range(30, 34):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})'''

if old_cap_fmt in src:
    src = src.replace(old_cap_fmt, new_cap_fmt)
    print("[OK] КАПИТАЛ: формат блоков 3 и 4")
else:
    print("[?] Не нашёл блок форматирования ПРОГНОЗ/ОБОРОТ")

# === 6. КАПИТАЛ: заголовок блока 4 в build_capital сдвинут с 27 на 29 ===
# Проверим: в build_capital блок 4 называется "4. ОБОРОТ ДЕНЕГ"
# Сейчас в коде должно быть так: 
#   блок 3: 4 строки (заголовок + 3 data) = кончается на 24
#   блок 4 начинается на 25 — не 27!
# Перепишем блок 4 в build_capital

old_cap_build = '''    # Блок 4. ОБОРОТ
    data.append(["4. ОБОРОТ ДЕНЕГ (за 30 дней)", "", "", "", ""])
    data.append(["Метрика", "Значение", "", "Комментарий", ""])
    data.append(["Вложили в закупку", f"{cogs_30:,.0f} руб", "", "себестоимость проданного", ""])
    data.append(["Получили выручки", f"{revenue_30:,.0f} руб", "", "", ""])
    data.append(["Оборот", f"{turnover:.2f}x", "",
                 "во сколько раз прокрутился рубль", ""])
    data.append(["Дней на оборот", f"{days_per_turn:.0f}", "",
                 "вложил → получил", ""])
    return data'''

new_cap_build = '''    # Блок 4. ОБОРОТ
    data.append(["", "", "", "", ""])  # пустая
    data.append(["4. ОБОРОТ ДЕНЕГ (за 30 дней)", "", "", "", ""])
    data.append(["Метрика", "Значение", "", "Комментарий", ""])
    data.append(["Вложили в закупку", f"{cogs_30:,.0f} руб", "", "себестоимость проданного", ""])
    data.append(["Получили выручки", f"{revenue_30:,.0f} руб", "", "", ""])
    data.append(["Оборот", f"{turnover:.2f}x", "",
                 "во сколько раз прокрутился рубль", ""])
    data.append(["Дней на оборот", f"{days_per_turn:.0f}", "",
                 "вложил → получил", ""])
    return data'''

if old_cap_build in src:
    src = src.replace(old_cap_build, new_cap_build)
    print("[OK] КАПИТАЛ: пустая строка перед блоком 4")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
