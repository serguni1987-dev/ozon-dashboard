"""
patch_today_center.py — центрирование элементов листа СЕГОДНЯ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Заголовок A1 — центр ===
src = src.replace(
    '''FMT_TITLE = CellFormat(
    backgroundColor=HEADER_BG,
    textFormat=TextFormat(foregroundColor=HEADER_FG, bold=True, fontSize=14),
    horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
)''',
    '''FMT_TITLE = CellFormat(
    backgroundColor=HEADER_BG,
    textFormat=TextFormat(foregroundColor=HEADER_FG, bold=True, fontSize=14),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)'''
)

# === 2. Статус свежести A4 — центр ===
src = src.replace(
    '''FMT_STATUS = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11),
    verticalAlignment='MIDDLE',
)''',
    '''FMT_STATUS = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)'''
)

# === 3. Подзаголовки (ПОКАЗАТЕЛИ / ТОП-5 / КУДА СМОТРЕТЬ) — центр ===
src = src.replace(
    '''FMT_SUBHEADER = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=Color(0.2, 0.2, 0.2)),
    verticalAlignment='MIDDLE', horizontalAlignment='LEFT',
)''',
    '''FMT_SUBHEADER = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=Color(0.2, 0.2, 0.2)),
    verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
)'''
)

# === 4. Метки (Выручка, Заказы, Активных SKU) — центр ===
src = src.replace(
    '''FMT_LABEL = CellFormat(
    textFormat=TextFormat(fontSize=11, bold=True),
    horizontalAlignment='LEFT',
)''',
    '''FMT_LABEL = CellFormat(
    textFormat=TextFormat(fontSize=11, bold=True),
    horizontalAlignment='CENTER',
)'''
)

# === 5. Значения 16pt — центр ===
src = src.replace(
    '''FMT_VALUE = CellFormat(
    textFormat=TextFormat(fontSize=16, bold=True),
    horizontalAlignment='RIGHT',
)''',
    '''FMT_VALUE = CellFormat(
    textFormat=TextFormat(fontSize=16, bold=True),
    horizontalAlignment='CENTER',
)'''
)

src = src.replace(
    '''FMT_VALUE_SMALL = CellFormat(
    textFormat=TextFormat(fontSize=14, bold=True),
    horizontalAlignment='RIGHT',
)''',
    '''FMT_VALUE_SMALL = CellFormat(
    textFormat=TextFormat(fontSize=14, bold=True),
    horizontalAlignment='CENTER',
)'''
)

# === 6. Вердикт — центр ===
src = src.replace(
    '''FMT_VERDICT_GOOD = CellFormat(
    backgroundColor=GOOD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=GOOD_FG),
    horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
)''',
    '''FMT_VERDICT_GOOD = CellFormat(
    backgroundColor=GOOD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=GOOD_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)'''
)
src = src.replace(
    '''FMT_VERDICT_BAD = CellFormat(
    backgroundColor=BAD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=BAD_FG),
    horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
)''',
    '''FMT_VERDICT_BAD = CellFormat(
    backgroundColor=BAD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=BAD_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)'''
)
src = src.replace(
    '''FMT_VERDICT_NEUTRAL = CellFormat(
    backgroundColor=WARN_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.5, 0.4, 0.0)),
    horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
)''',
    '''FMT_VERDICT_NEUTRAL = CellFormat(
    backgroundColor=WARN_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.5, 0.4, 0.0)),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)'''
)

# === 7. Заголовки колонок метрик — все центр ===
src = src.replace(
    '''    ops.append({"type": "format", "range": "A7", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "B7:C7", "format": fmt_hdr_right})
    ops.append({"type": "format", "range": "D7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "E7", "format": fmt_hdr_left})''',
    '''    ops.append({"type": "format", "range": "A7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "B7:C7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "D7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "E7", "format": fmt_hdr_center})'''
)

# === 8. ТОП-5 заголовки — все центр ===
src = src.replace(
    '''    ops.append({"type": "format", "range": "A14:B14", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "C14", "format": fmt_hdr_right})
    ops.append({"type": "format", "range": "D14", "format": fmt_hdr_center})''',
    '''    ops.append({"type": "format", "range": "A14:D14", "format": fmt_hdr_center})'''
)

# === 9. ТОП-5 значения — все центр ===
src = src.replace(
    '''    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True))
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=10))
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='RIGHT')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')''',
    '''    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')'''
)

# === 10. Хинты (колонка E) — центр ===
src = src.replace(
    '''FMT_HINT = CellFormat(
    textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
    horizontalAlignment='LEFT', wrapStrategy='WRAP',
)''',
    '''FMT_HINT = CellFormat(
    textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
)'''
)

# === 11. Строки блока "Куда смотреть" — центр ===
src = src.replace(
    '''    fmt_action = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT',
        verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )''',
    '''    fmt_action = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER',
        verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )'''
)

# === 12. Увеличиваем высоту строк метрик и ТОП-5, чтобы текст не обрезался ===
src = src.replace(
    '''    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": fmt_action})
        ops.append({"type": "row_height", "row": r, "height": 32})''',
    '''    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": fmt_action})
        ops.append({"type": "row_height", "row": r, "height": 36})

    # Высота строк метрик (чтобы колонка E не обрезалась)
    for r in (8, 9, 10):
        ops.append({"type": "row_height", "row": r, "height": 44})

    # Высота строки заголовков
    ops.append({"type": "row_height", "row": 1, "height": 40})
    ops.append({"type": "row_height", "row": 6, "height": 26})'''
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] Центрирование применено")
print("Запускай: py sheets_sync.py")
