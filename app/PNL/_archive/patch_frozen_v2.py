src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. Итоги — БЕЗ merge, простые колонки A/B/C ============
old_totals = '''    ops.append({"type": "merge", "range": "A4:I4"})
    ops.append({"type": "format", "range": "A4:I4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           backgroundColor=SUBHEADER_BG)
    big_num = CellFormat(textFormat=TextFormat(bold=True, fontSize=14,
                                                foregroundColor=Color(0.1, 0.3, 0.6)),
                         horizontalAlignment='LEFT', verticalAlignment='MIDDLE')
    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 30})
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "format", "range": f"A{r}:B{r}", "format": label_fmt})
        ops.append({"type": "merge", "range": f"C{r}:E{r}"})
        ops.append({"type": "format", "range": f"C{r}:E{r}", "format": big_num})
        ops.append({"type": "format", "range": f"F{r}:I{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})'''

new_totals = '''    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    # Столбец A — подпись, B — значение, C — пояснение
    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           backgroundColor=SUBHEADER_BG)
    big_num = CellFormat(textFormat=TextFormat(bold=True, fontSize=14,
                                                foregroundColor=Color(0.1, 0.3, 0.6)),
                         horizontalAlignment='LEFT', verticalAlignment='MIDDLE')
    note_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                 foregroundColor=MUTED_FG),
                          horizontalAlignment='LEFT', verticalAlignment='MIDDLE')
    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 30})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})'''

if old_totals in src:
    src = src.replace(old_totals, new_totals)
    print("[OK] Итоги: без merge, A/B/C раздельно")

# ============ 2. Данные 11-40 — БЕЗ колонки I (индекс в H) ============
old_rows = '''    for r in range(11, 41):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "format", "range": f"I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})'''

new_rows = '''    for r in range(11, 41):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})'''

if old_rows in src:
    src = src.replace(old_rows, new_rows)
    print("[OK] Данные: без колонки I")

# ============ 3. Цвет индексов — в H (не I) ============
old_color = '''        vals = ws.get("I11:I40")'''
new_color = '''        vals = ws.get("H11:H40")'''
if old_color in src:
    src = src.replace(old_color, new_color)
    print("[OK] Чтение индекса: I → H")

src = src.replace(
    'ops2.append({"type": "format", "range": f"I{11+i}", "format": color_fmt[c]})',
    'ops2.append({"type": "format", "range": f"H{11+i}", "format": color_fmt[c]})'
)
print("[OK] Покраска индекса: I → H")

# ============ 4. Заголовок ТОП-30 — обратно до H ============
src = src.replace(
    'ops.append({"type": "merge", "range": "A9:I9"})',
    'ops.append({"type": "merge", "range": "A9:H9"})'
)
src = src.replace(
    'ops.append({"type": "format", "range": "A9:I9", "format": FMT_SUBHEADER})',
    'ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})'
)
src = src.replace(
    'ops.append({"type": "format", "range": "A10:I10", "format": tbl_hdr})',
    'ops.append({"type": "format", "range": "A10:H10", "format": tbl_hdr})'
)
print("[OK] Заголовки вернулись к H")

# ============ 5. Ширины — убираем I ============
src = src.replace(
    '''    for c, w in [("A", 40), ("B", 140), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 130), ("I", 130)]:
        ops.append({"type": "width", "col": c, "width": w})''',
    '''    for c, w in [("A", 40), ("B", 150), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})'''
)
print("[OK] Ширины A-H")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
