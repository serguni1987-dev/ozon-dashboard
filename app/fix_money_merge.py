src = open("sheets_sync.py", encoding="utf-8").read()

# Добавляем полный unmerge в начало format_money
old = '''def format_money(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})'''

new = '''def format_money(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] format_money: unmerge расширен до Z100")
else:
    print("[?] Не нашёл начало format_money")

# Также — перед merge для ВЫВОДОВ явно размёрживаем ту область
old2 = '''    # ВЫВОДЫ — 16
    ops.append({"type": "merge", "range": "A16:J16"})
    ops.append({"type": "format", "range": "A16:J16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    for r in range(17, 22):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})'''

new2 = '''    # ВЫВОДЫ — 16
    # Явно размёрживаем всё перед merge
    for r in range(16, 22):
        ops.append({"type": "unmerge", "range": f"A{r}:J{r}"})
    ops.append({"type": "merge", "range": "A16:J16"})
    ops.append({"type": "format", "range": "A16:J16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    for r in range(17, 22):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Явный unmerge A16:J22 перед merge выводов")
else:
    print("[?] Не нашёл блок ВЫВОДЫ")

# И для таблицы периодов — тоже
old3 = '''    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})'''

new3 = '''    # Размёрживаем строки 4-14 перед merge
    for r in range(4, 15):
        ops.append({"type": "unmerge", "range": f"A{r}:J{r}"})
    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})'''

if old3 in src:
    src = src.replace(old3, new3, 1)
    print("[OK] Явный unmerge A4:J14")

# Цвет выводов — оставить, B17:B21
print()
open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("Готово. Запускай: py sheets_sync.py")
