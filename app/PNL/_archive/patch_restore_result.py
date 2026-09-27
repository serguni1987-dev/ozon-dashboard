"""
patch_restore_result.py — восстанавливает format_result и sync_result.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

if "def sync_result" in src:
    print("[i] sync_result уже есть")
    exit(0)

new_block = '''
def format_result(ws):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    # Заголовок A1:D1
    ops.append({"type": "merge", "range": "A1:D1"})
    ops.append({"type": "format", "range": "A1:D1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок A2:D2
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:D2"})
    ops.append({"type": "format", "range": "A2:D2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки A4:D4
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:D4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    # Данные 5-9
    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_val = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_delta = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    for r in range(5, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": body_val})
        ops.append({"type": "format", "range": f"D{r}", "format": body_delta})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Прошлый запуск — строка 11
    last_run = CellFormat(
        textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A11:D11"})
    ops.append({"type": "format", "range": "A11:D11", "format": last_run})
    ops.append({"type": "row_height", "row": 11, "height": 24})

    ops.append({"type": "width", "col": "A", "width": 180})
    ops.append({"type": "width", "col": "B", "width": 160})
    ops.append({"type": "width", "col": "C", "width": 160})
    ops.append({"type": "width", "col": "D", "width": 120})

    ops.append({"type": "frozen", "rows": 4})

    ops.append({"type": "note", "cell": "D4",
                "note": "Δ = изменение vs прошлый запуск. Зелёный: рост, красный: падение."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Δ-цвета
    try:
        values = ws.get("D5:D9")
        ops2 = []
        for i, row in enumerate(values):
            if not row:
                continue
            v = row[0].strip()
            r = 5 + i
            if v.startswith("+") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=GOOD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=GOOD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
            elif v.startswith("-") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=BAD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
        if ops2:
            n2 = batch_apply(ws, sid, ops2)
            print(f"  Δ-цвета: {n2}")
    except Exception as e:
        print(f"  [WARN] Δ-цвета: {e}")


def sync_result(sh, con):
    print("\\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)


'''

anchor = "def main():"
if anchor in src:
    src = src.replace(anchor, new_block + anchor, 1)
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] format_result + sync_result восстановлены")
else:
    print("[FAIL] Не нашёл main()")
