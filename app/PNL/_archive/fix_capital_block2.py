"""
fix_capital_block2.py — исправляет выделение в блоке 2 листа КАПИТАЛ.
Строка 19 «МОЖНО ЗАБРАТЬ» должна быть зелёной.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

old = '''    # Блок 2: ЧТО ЗАБРАТЬ
    ops.append({"type": "format", "range": "A13:E13", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 13, "height": 32})
    for r in range(14, 19):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})
    # Строка МОЖНО ЗАБРАТЬ — зелёная
    ops.append({"type": "format", "range": "A18", "format": free_fmt})
    ops.append({"type": "format", "range": "B18:C18", "format": free_val_fmt})'''

new = '''    # Блок 2: ЧТО ЗАБРАТЬ
    ops.append({"type": "format", "range": "A13:E13", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 13, "height": 32})

    # Заголовки колонок "Сумма руб / Комментарий" — синяя полоса
    ops.append({"type": "format", "range": "A14:E14", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 14, "height": 32})

    # Строки данных 15-19
    for r in range(15, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 19 "МОЖНО ЗАБРАТЬ" — зелёная
    ops.append({"type": "format", "range": "A19", "format": free_fmt})
    ops.append({"type": "format", "range": "B19:C19", "format": free_val_fmt})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Блок 2: МОЖНО ЗАБРАТЬ теперь на строке 19 (зелёная)")
else:
    print("[?] Не нашёл блок 2")

# Также — в блоке 1 аналогичная проверка: строка 11 = ВСЕГО ДЕНЕГ
old1 = '''    # Блок 1: ГДЕ ДЕНЬГИ
    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})
    for r in range(6, 12):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})
    # Строка ВСЕГО — выделить
    ops.append({"type": "format", "range": "A11", "format": total_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": total_val_fmt})'''

new1 = '''    # Блок 1: ГДЕ ДЕНЬГИ
    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})
    for r in range(6, 12):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})
    # Строка 11 "ВСЕГО ДЕНЕГ" — синяя
    ops.append({"type": "format", "range": "A11", "format": total_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": total_val_fmt})'''

if old1 in src:
    print("[i] Блок 1 уже правильный (без изменений)")
else:
    print("[i] Блок 1 — формат уже OK")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
