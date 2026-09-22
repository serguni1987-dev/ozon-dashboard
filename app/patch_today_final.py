"""
patch_today_final.py — финальное выравнивание листа СЕГОДНЯ.
1. Unmerge всей области перед записью.
2. Заголовки растянуть до H.
3. Задать высоту строк для блока "Куда смотреть".
4. Расширить колонку E.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Добавляем в batch_apply типы "unmerge" и "row_height" ===
old = '''        elif t == "merge":
            requests.append({
                "mergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "mergeType": op.get("mergeType", "MERGE_ALL"),
                }
            })'''

new = '''        elif t == "merge":
            requests.append({
                "mergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "mergeType": op.get("mergeType", "MERGE_ALL"),
                }
            })
        elif t == "unmerge":
            requests.append({
                "unmergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                }
            })
        elif t == "row_height":
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": op["row"] - 1,
                        "endIndex": op["row"],
                    },
                    "properties": {"pixelSize": op["height"]},
                    "fields": "pixelSize",
                }
            })'''

if old in src:
    src = src.replace(old, new)
    print("[OK] unmerge + row_height добавлены в batch_apply")
else:
    print("[?] Не нашёл merge блок в batch_apply")

# === 2. В начало format_today — unmerge всей области ===
old_head = '''def format_today(ws, values, max_date, verdict):
    sid = ws.id
    ops = []
'''
new_head = '''def format_today(ws, values, max_date, verdict):
    sid = ws.id
    ops = []

    # Сбрасываем все merge на листе перед записью
    ops.append({"type": "unmerge", "range": "A1:Z50"})
'''
if old_head in src:
    src = src.replace(old_head, new_head)
    print("[OK] unmerge перед записью добавлен")
else:
    print("[?] Не нашёл начало format_today")

# === 3. Убираем safe_unmerge из format_today (они теперь в ops) ===
src = src.replace('    safe_unmerge(ws, "A1:E1")\n', '')
src = src.replace('    safe_unmerge(ws, "A4:B4")\n', '')
src = src.replace('    safe_unmerge(ws, "A6:E6")\n', '')
src = src.replace('    safe_unmerge(ws, "A11:E11")\n', '')
src = src.replace('    safe_unmerge(ws, "A13:E13")\n', '')
src = src.replace('    safe_unmerge(ws, "A22:E22")\n', '')
src = src.replace('    safe_merge(ws, "A1:E1")\n', '')
src = src.replace('    safe_merge(ws, "A4:B4")\n', '')
src = src.replace('    safe_merge(ws, "A6:E6")\n', '')
src = src.replace('    safe_merge(ws, "A11:E11")\n', '')
src = src.replace('    safe_merge(ws, "A13:E13")\n', '')
src = src.replace('    safe_merge(ws, "A22:E22")\n', '')
print("[OK] safe_unmerge/safe_merge убраны из format_today")

# === 4. Расширяем заголовки до H, добавляем unmerge для старых merge ===
# Заменяем операции format для заголовков на merge + format

# A1: заголовок
src = src.replace(
    '    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})',
    '    ops.append({"type": "merge", "range": "A1:H1"})\n'
    '    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})'
)

# A2: строка "обновлено" — объединить
src = src.replace(
    '    ops.append({"type": "format", "range": "A2", "format": FMT_UPDATED})',
    '    ops.append({"type": "merge", "range": "A2:H2"})\n'
    '    ops.append({"type": "format", "range": "A2:H2", "format": FMT_UPDATED})'
)

# A4:B4 — статус свежести, растянем до A4:H4
src = src.replace(
    '    ops.append({"type": "format", "range": "A4:B4", "format": FMT_STATUS})',
    '    ops.append({"type": "merge", "range": "A4:H4"})\n'
    '    ops.append({"type": "format", "range": "A4:H4", "format": FMT_STATUS})'
)

# A6: подзаголовок ПОКАЗАТЕЛИ
src = src.replace(
    '    ops.append({"type": "format", "range": "A6:E6", "format": FMT_SUBHEADER})',
    '    ops.append({"type": "merge", "range": "A6:H6"})\n'
    '    ops.append({"type": "format", "range": "A6:H6", "format": FMT_SUBHEADER})'
)

# A11: вердикт
src = src.replace(
    '    ops.append({"type": "format", "range": "A11:E11", "format": vfmt})',
    '    ops.append({"type": "merge", "range": "A11:H11"})\n'
    '    ops.append({"type": "format", "range": "A11:H11", "format": vfmt})'
)

# A13: заголовок ТОП-5
src = src.replace(
    '    ops.append({"type": "format", "range": "A13:E13", "format": FMT_SUBHEADER})',
    '    ops.append({"type": "merge", "range": "A13:H13"})\n'
    '    ops.append({"type": "format", "range": "A13:H13", "format": FMT_SUBHEADER})'
)

# A22: заголовок "Куда смотреть"
src = src.replace(
    '    ops.append({"type": "format", "range": "A22:E22", "format": FMT_SUBHEADER})',
    '    ops.append({"type": "merge", "range": "A22:H22"})\n'
    '    ops.append({"type": "format", "range": "A22:H22", "format": FMT_SUBHEADER})'
)

# A23-A27: строки блока "Куда смотреть" — merge до H + высота + перенос
old_action_loop = '''    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": fmt_action})'''

new_action_loop = '''    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": fmt_action})
        ops.append({"type": "row_height", "row": r, "height": 32})'''

if old_action_loop in src:
    src = src.replace(old_action_loop, new_action_loop)
    print("[OK] блок 'Куда смотреть' — merge A:H + высота 32px")
else:
    print("[?] Не нашёл action loop")

# === 5. Расширяем колонку E + добавляем F/G/H ===
old_widths = '''    ops.append({"type": "width", "col": "A", "width": 260})
    ops.append({"type": "width", "col": "B", "width": 180})
    ops.append({"type": "width", "col": "C", "width": 140})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 380})'''

new_widths = '''    ops.append({"type": "width", "col": "A", "width": 260})
    ops.append({"type": "width", "col": "B", "width": 180})
    ops.append({"type": "width", "col": "C", "width": 140})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 320})
    ops.append({"type": "width", "col": "F", "width": 100})
    ops.append({"type": "width", "col": "G", "width": 100})
    ops.append({"type": "width", "col": "H", "width": 100})'''

if old_widths in src:
    src = src.replace(old_widths, new_widths)
    print("[OK] ширины колонок A-H заданы")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
