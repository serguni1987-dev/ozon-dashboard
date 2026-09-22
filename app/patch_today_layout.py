"""
patch_today_layout.py — исправляет выравнивание и объединяет строки
в блоке «КУДА СМОТРЕТЬ СЕЙЧАС».
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Добавляем поддержку "merge" в batch_apply ===
old_apply = '''        elif t == "note":
            requests.append({
                "updateCells": {
                    "range": _a1_to_grid_range(op["cell"], sheet_id),
                    "rows": [{"values": [{"note": op["note"]}]}],
                    "fields": "note",
                }
            })'''

new_apply = '''        elif t == "note":
            requests.append({
                "updateCells": {
                    "range": _a1_to_grid_range(op["cell"], sheet_id),
                    "rows": [{"values": [{"note": op["note"]}]}],
                    "fields": "note",
                }
            })
        elif t == "merge":
            requests.append({
                "mergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "mergeType": op.get("mergeType", "MERGE_ALL"),
                }
            })'''

if old_apply in src:
    src = src.replace(old_apply, new_apply)
    print("[OK] merge добавлен в batch_apply")
else:
    print("[?] Не нашёл блок note в batch_apply")

# === 2. В format_today — добавляем merge для блока "Куда смотреть" ===
old_block = '''    # Блок "Куда смотреть" — заголовок + содержимое
    safe_unmerge(ws, "A22:E22")
    safe_merge(ws, "A22:E22")
    ops.append({"type": "format", "range": "A22:E22", "format": FMT_SUBHEADER})
    for r in range(23, 28):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": FMT_ACTION_ITEM})'''

new_block = '''    # Блок "Куда смотреть" — заголовок + содержимое
    safe_unmerge(ws, "A22:E22")
    safe_merge(ws, "A22:E22")
    ops.append({"type": "format", "range": "A22:E22", "format": FMT_SUBHEADER})

    # Строки 23-27: объединяем A:E и выравниваем по левому краю с переносом
    fmt_action = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT',
        verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": fmt_action})'''

if old_block in src:
    src = src.replace(old_block, new_block)
    print("[OK] блок 'Куда смотреть' обновлён")
else:
    print("[?] Не нашёл блок 'Куда смотреть'")

# === 3. Выравнивание заголовков колонок в ТОП-5 ===
old_top_hdr = '''    ops.append({"type": "format", "range": "A13:E13", "format": FMT_SUBHEADER})
    ops.append({"type": "format", "range": "A14:D14", "format": FMT_COLHEADER})'''

new_top_hdr = '''    ops.append({"type": "format", "range": "A13:E13", "format": FMT_SUBHEADER})
    # Заголовки ТОП-5: A, B — по левому; C, D — выровнены со значениями ниже
    fmt_hdr_left = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='LEFT',
    )
    fmt_hdr_right = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='RIGHT',
    )
    fmt_hdr_center = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER',
    )
    ops.append({"type": "format", "range": "A14:B14", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "C14", "format": fmt_hdr_right})
    ops.append({"type": "format", "range": "D14", "format": fmt_hdr_center})'''

if old_top_hdr in src:
    src = src.replace(old_top_hdr, new_top_hdr)
    print("[OK] заголовки ТОП-5 выровнены")
else:
    print("[?] Не нашёл блок заголовков ТОП-5")

# === 4. Заголовки в блоке ПОКАЗАТЕЛИ — тоже выровнять ===
old_metrics_hdr = '''    ops.append({"type": "format", "range": "A6:E6", "format": FMT_SUBHEADER})
    ops.append({"type": "format", "range": "A7:E7", "format": FMT_COLHEADER})'''

new_metrics_hdr = '''    ops.append({"type": "format", "range": "A6:E6", "format": FMT_SUBHEADER})
    # Заголовки метрик: A — left, B/C — right (как значения), D — center
    ops.append({"type": "format", "range": "A7", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "B7:C7", "format": fmt_hdr_right})
    ops.append({"type": "format", "range": "D7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "E7", "format": fmt_hdr_left})'''

if old_metrics_hdr in src:
    src = src.replace(old_metrics_hdr, new_metrics_hdr)
    print("[OK] заголовки метрик выровнены")
else:
    print("[?] Не нашёл блок заголовков метрик")

# === 5. Убедимся, что fmt_hdr_* определены ДО первого использования ===
# Они определяются в блоке ТОП-5, а используются в метриках (выше). Переставляем.
# Проще: определить их в самом начале format_today.
marker = "def format_today(ws, values, max_date, verdict):\n    sid = ws.id\n    ops = []"
replacement = '''def format_today(ws, values, max_date, verdict):
    sid = ws.id
    ops = []

    # Общие форматы заголовков
    fmt_hdr_left = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='LEFT',
    )
    fmt_hdr_right = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='RIGHT',
    )
    fmt_hdr_center = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER',
    )'''

if marker in src:
    src = src.replace(marker, replacement)
    print("[OK] fmt_hdr_* вынесены наверх")

# Теперь убираем дублирующее определение в блоке ТОП-5
dup = '''    # Заголовки ТОП-5: A, B — по левому; C, D — выровнены со значениями ниже
    fmt_hdr_left = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='LEFT',
    )
    fmt_hdr_right = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='RIGHT',
    )
    fmt_hdr_center = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER',
    )
    ops.append({"type": "format", "range": "A14:B14", "format": fmt_hdr_left})'''
replacement2 = '''    ops.append({"type": "format", "range": "A14:B14", "format": fmt_hdr_left})'''
if dup in src:
    src = src.replace(dup, replacement2)
    print("[OK] убрано дублирование fmt_hdr_*")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
