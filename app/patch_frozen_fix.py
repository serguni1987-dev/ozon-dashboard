src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. Итоги — смещаем в A:B, расширяем A ============
old_totals = '''    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           backgroundColor=SUBHEADER_BG)
    big_num = CellFormat(textFormat=TextFormat(bold=True, fontSize=14,
                                                foregroundColor=Color(0.1, 0.3, 0.6)),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 28})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})'''

new_totals = '''    ops.append({"type": "merge", "range": "A4:I4"})
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

if old_totals in src:
    src = src.replace(old_totals, new_totals)
    print("[OK] Итоги: A:B + C:E + расширение до I")

# ============ 2. Заголовок ТОП-30 растягиваем до I ============
src = src.replace(
    'ops.append({"type": "merge", "range": "A9:H9"})',
    'ops.append({"type": "merge", "range": "A9:I9"})'
)
src = src.replace(
    'ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})',
    'ops.append({"type": "format", "range": "A9:I9", "format": FMT_SUBHEADER})'
)
print("[OK] ТОП-30 растянут до I")

# Заголовок таблицы
src = src.replace(
    'ops.append({"type": "format", "range": "A10:H10", "format": tbl_hdr})',
    'ops.append({"type": "format", "range": "A10:I10", "format": tbl_hdr})'
)

# Данные 11-40 — колонки до I
old_rows = '''    for r in range(11, 41):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
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
        ops.append({"type": "format", "range": f"I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})'''

if old_rows in src:
    src = src.replace(old_rows, new_rows)
    print("[OK] Данные 11-40 — добавлена колонка I")

# ============ 3. Ширины — добавить I ============
old_w = '''    for c, w in [("A", 40), ("B", 140), ("C", 400), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 130)]:
        ops.append({"type": "width", "col": c, "width": w})'''

new_w = '''    for c, w in [("A", 40), ("B", 140), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 130), ("I", 130)]:
        ops.append({"type": "width", "col": c, "width": w})'''

if old_w in src:
    src = src.replace(old_w, new_w)
    print("[OK] Ширины: колонка I = 130")

# ============ 4. Цвет индексов — из H переводим в I ============
old_color = '''    try:
        vals = ws.get("H11:H40")
        color_fmt = {
            "RED":   CellFormat(backgroundColor=BAD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                horizontalAlignment='CENTER'),
            "SUPER": CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                horizontalAlignment='CENTER'),
            "GREEN": CellFormat(backgroundColor=GOOD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                horizontalAlignment='CENTER'),
        }
        ops2 = []
        for i, row in enumerate(vals):
            c = (row[0] or "").strip() if row else ""
            if c in color_fmt:
                ops2.append({"type": "format", "range": f"H{11+i}", "format": color_fmt[c]})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет индексов: {len(ops2)}")
    except Exception as e:
        print(f"  [WARN] Цвет: {e}")'''

new_color = '''    try:
        vals = ws.get("I11:I40")
        color_fmt = {
            "RED":          CellFormat(backgroundColor=BAD_BG,
                                       textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                       horizontalAlignment='CENTER'),
            "SUPER":        CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                       textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                       horizontalAlignment='CENTER'),
            "GREEN":        CellFormat(backgroundColor=GOOD_BG,
                                       textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                       horizontalAlignment='CENTER'),
            "YELLOW":       CellFormat(backgroundColor=WARN_BG,
                                       textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                       horizontalAlignment='CENTER'),
            "WITHOUT_INDEX": CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                              foregroundColor=MUTED_FG),
                                        horizontalAlignment='CENTER'),
        }
        ops2 = []
        for i, row in enumerate(vals):
            c = (row[0] or "").strip() if row else ""
            if c in color_fmt:
                ops2.append({"type": "format", "range": f"I{11+i}", "format": color_fmt[c]})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет индексов: {len(ops2)}")
    except Exception as e:
        print(f"  [WARN] Цвет: {e}")'''

if old_color in src:
    src = src.replace(old_color, new_color)
    print("[OK] Цвет индексов: H → I")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
