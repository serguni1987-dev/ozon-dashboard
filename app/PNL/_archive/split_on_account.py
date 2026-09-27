"""
split_on_account.py — разделяем строки "На счету" и "У Ozon к выплате" в листе КАПИТАЛ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. В build_capital — разделяем строку
old = '''    data.append(["На счету + у Ozon", f"{on_account + owed_by_ozon:,.0f}", "",
                 "что можно получить", ""])'''

new = '''    data.append(["На счету (в руках)", f"{on_account:,.0f}", "",
                 "уже доступно", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", "",
                 "придёт в течение недели", ""])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Разделили 'На счету' и 'У Ozon'")
else:
    print("[?] Не нашёл строку в build_capital")

# 2. В format_capital — теперь строк 6 вместо 5, сдвигаем
# Было: 15 заголовок, 16-19 данные, 20 МОЖНО ЗАБРАТЬ
# Стало: 15 заголовок, 16-20 данные (5), 21 МОЖНО ЗАБРАТЬ

old_fmt = '''    ops.append({"type": "format", "range": "A15:E15", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(16, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 20 — МОЖНО ЗАБРАТЬ (зелёная)
    ops.append({"type": "format", "range": "A20", "format": free_fmt})
    ops.append({"type": "format", "range": "B20:C20", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 20, "height": 34})'''

new_fmt = '''    ops.append({"type": "format", "range": "A15:E15", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(16, 21):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 21 — МОЖНО ЗАБРАТЬ (зелёная)
    ops.append({"type": "format", "range": "A21", "format": free_fmt})
    ops.append({"type": "format", "range": "B21:C21", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 21, "height": 34})'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] format_capital: сдвиг строк")

# 3. Сдвигаем блок 3 и блок 4 на одну строку вниз
src = src.replace('"range": "A22:E22"', '"range": "A23:E23"')  # заголовок блока 3
src = src.replace('"range": "A23:E23", "format": tbl_hdr', '"range": "A24:E24", "format": tbl_hdr')  # заголовки
src = src.replace('for r in range(24, 29):', 'for r in range(25, 30):')  # данные
src = src.replace('"range": "A30:E30"', '"range": "A31:E31"')  # заголовок блока 4
src = src.replace('"range": "A31:E31", "format": tbl_hdr', '"range": "A32:E32", "format": tbl_hdr')  # заголовки
src = src.replace('for r in range(32, 36):', 'for r in range(33, 37):')  # данные
src = src.replace('"range": "A37:E37"', '"range": "A38:E38"')  # заголовок выводов
src = src.replace('for r in range(38, 45):', 'for r in range(39, 46):')
src = src.replace('vals = ws.get("A38:A44")', 'vals = ws.get("A39:A45")')
src = src.replace('r = 38 + i', 'r = 39 + i')

print("[OK] format_capital: блоки 3-5 сдвинуты на 1 строку")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("Готово. Запускай: py sheets_sync.py")
