src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Колонка B (Название) — шире
src = src.replace(
    'ops.append({"type": "width", "col": "B", "width": 420})',
    'ops.append({"type": "width", "col": "B", "width": 600})'
)

# 2. Названия в ТОП-5 — выравнивание по ЛЕВОМУ краю (чтобы читались с начала)
src = src.replace(
    '''    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')''',
    '''    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=9),
                           horizontalAlignment='LEFT', wrapStrategy='WRAP')
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')'''
)

# 3. Высота строк ТОП-5 — больше, чтобы длинные названия не резались
src = src.replace(
    '''    ops.append({"type": "row_height", "row": 1, "height": 40})
    ops.append({"type": "row_height", "row": 6, "height": 26})''',
    '''    ops.append({"type": "row_height", "row": 1, "height": 40})
    ops.append({"type": "row_height", "row": 6, "height": 26})
    # ТОП-5 — высота строк 15-19
    for r in range(15, 20):
        ops.append({"type": "row_height", "row": r, "height": 36})'''
)

# 4. Заголовок ТОП-5 «Название» — по левому краю (как и значения)
src = src.replace(
    '''    ops.append({"type": "format", "range": "A14:D14", "format": fmt_hdr_center})''',
    '''    ops.append({"type": "format", "range": "A14", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "B14", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "C14:D14", "format": fmt_hdr_center})'''
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] Финальная полировка ТОП-5 применена")
