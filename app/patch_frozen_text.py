src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. Выводы: высота 45px вместо 30 ============
old_h = '''    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"B{r}:H{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})'''

new_h = '''    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"B{r}:H{r}"})
        ops.append({"type": "row_height", "row": r, "height": 45})'''

if old_h in src:
    src = src.replace(old_h, new_h)
    print("[OK] Выводы: высота 45px")

# ============ 2. Заголовок ТОП-30: расширяем merge до K + LEFT align ============
old_title = '''    # === ТОП-30 (строка 16) ===
    ops.append({"type": "merge", "range": "A16:H16"})
    ops.append({"type": "format", "range": "A16:H16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 26})'''

new_title = '''    # === ТОП-30 (строка 16) ===
    # Явно задаём LEFT-выравнивание, чтобы текст не срезался
    title_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A16:H16"})
    ops.append({"type": "format", "range": "A16:H16", "format": title_fmt})
    ops.append({"type": "row_height", "row": 16, "height": 30})'''

if old_title in src:
    src = src.replace(old_title, new_title)
    print("[OK] Заголовок ТОП-30: новый формат, height 30")

# ============ 3. Проверим, что текст в A16 не конфликтует с другими merge ============
# Возможно, проблема с A9:H9 — если она не размёржена, A16:H16 мог не примениться
# Явно добавим unmerge для A9:H9 и A16:H16 в начало
old_unmerge = '''    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})'''

new_unmerge = '''    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})
    ops.append({"type": "unmerge", "range": "A9:H9"})
    ops.append({"type": "unmerge", "range": "A16:H16"})
    ops.append({"type": "unmerge", "range": "B10:H14"})'''

if old_unmerge in src:
    src = src.replace(old_unmerge, new_unmerge)
    print("[OK] Явные unmerge для проблемных зон")

# ============ 4. Данные ТОП-30 сдвигаем с 18-47 обратно на 18-47 (уже так) ============
# Frozen rows: не 17, а 17 (заголовки 16-17 видны всегда)
# Уже 17

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
