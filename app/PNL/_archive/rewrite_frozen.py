import re
src = open("sheets_sync.py", encoding="utf-8").read()

# Удаляем format_frozen
pattern = re.compile(r"def format_frozen\(ws, items\):.*?(?=\ndef sync_frozen)", re.DOTALL)
src, n = pattern.subn("", src)
print(f"[OK] Старый format_frozen удалён: {n}")

# Новый format_frozen
new_func = '''def format_frozen(ws, items):
    sid = ws.id
    ops = []

    # Жёсткий сброс всего
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    ops.append({"type": "clear_notes", "range": "A1:Z200"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:H1"})
    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG, horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A2:H2"})
    ops.append({"type": "format", "range": "A2:H2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # === ИТОГИ — заголовок строки 4 ===
    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": section_fmt})
    ops.append({"type": "row_height", "row": 4, "height": 28})

    # === Итоги 5-7: A:B подпись, C значение, D пояснение ===
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
        ops.append({"type": "row_height", "row": r, "height": 32})
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "format", "range": f"A{r}:B{r}", "format": label_fmt})
        ops.append({"type": "merge", "range": f"C{r}:D{r}"})
        ops.append({"type": "format", "range": f"C{r}:D{r}", "format": big_num})
        ops.append({"type": "merge", "range": f"E{r}:H{r}"})
        ops.append({"type": "format", "range": f"E{r}:H{r}", "format": note_fmt})

    # === ВЫВОДЫ — заголовок строка 9 ===
    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": section_fmt})
    ops.append({"type": "row_height", "row": 9, "height": 28})

    # === Выводы 10-14 ===
    # Каждый в отдельной строке с merge A:H
    verdict_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP')
    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": verdict_fmt})
        ops.append({"type": "row_height", "row": r, "height": 40})

    # === ТОП-30 — заголовок строка 16 ===
    ops.append({"type": "merge", "range": "A16:H16"})
    ops.append({"type": "format", "range": "A16:H16", "format": section_fmt})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    # Заголовки таблицы — 17
    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A17:H17", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 17, "height": 32})

    # Данные ТОП-30 — 18-47
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_money = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')

    for r in range(18, 48):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})

    # Ширины
    for c, w in [("A", 40), ("B", 150), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 17})

    n = batch_apply(ws, sid, ops)
    print(f"  Основное форматирование: {n}")

    # Цвет выводов (10-14)
    try:
        vals = ws.get("A10:A14")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 10 + i
            if v.startswith("❌") or v.startswith("⚠") or v.startswith("🔴"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→ ИТОГ") or v.startswith("→"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            elif v.startswith("⏳"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"A{r}:H{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {len(ops2)}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")

    # Цвет индексов (H18:H47)
    try:
        vals = ws.get("H18:H47")
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
            "YELLOW": CellFormat(backgroundColor=WARN_BG,
                                 textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                 horizontalAlignment='CENTER'),
            "WITHOUT_INDEX": CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                              foregroundColor=MUTED_FG),
                                        horizontalAlignment='CENTER'),
        }
        ops3 = []
        for i, row in enumerate(vals):
            c = (row[0] or "").strip() if row else ""
            if c in color_fmt:
                ops3.append({"type": "format", "range": f"H{18+i}", "format": color_fmt[c]})
        if ops3:
            batch_apply(ws, sid, ops3)
            print(f"  Цвет индексов: {len(ops3)}")
    except Exception as e:
        print(f"  [WARN] Цвет: {e}")


'''

# Вставляем новый format_frozen перед sync_frozen
anchor = "def sync_frozen(sh, con):"
if anchor in src:
    src = src.replace(anchor, new_func + anchor, 1)
    print("[OK] Новый format_frozen вставлен")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
