src = open("sheets_sync.py", encoding="utf-8").read()

# 1. ИСПРАВИТЬ serv_pct: s30[4] → s30[3]
src = src.replace(
    "serv_pct = s30[4] / s30[0] if s30[0] else 0",
    "serv_pct = s30[3] / s30[0] if s30[0] else 0"
)
print("[OK] serv_pct: s30[4] -> s30[3]")

# 2. ИСПРАВИТЬ merge для месяцев: A10 → A9, сдвиг всего на -1
old_format = '''    # ПО МЕСЯЦАМ — 10
    ops.append({"type": "merge", "range": "A10:J10"})
    ops.append({"type": "format", "range": "A10:J10", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 10, "height": 28})

    ops.append({"type": "format", "range": "A11:J11", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 11, "height": 36})

    for r in range(12, 16):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — 17
    ops.append({"type": "merge", "range": "A17:J17"})
    ops.append({"type": "format", "range": "A17:J17", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 17, "height": 28})

    for r in range(18, 23):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Premium — 24
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A24:J24"})
    ops.append({"type": "format", "range": "A24:J24", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 24, "height": 26})'''

new_format = '''    # ПО МЕСЯЦАМ — строка 9
    ops.append({"type": "merge", "range": "A9:J9"})
    ops.append({"type": "format", "range": "A9:J9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 28})

    # Заголовки таблицы — 10
    ops.append({"type": "format", "range": "A10:J10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 36})

    for r in range(11, 15):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — 16
    ops.append({"type": "merge", "range": "A16:J16"})
    ops.append({"type": "format", "range": "A16:J16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    for r in range(17, 22):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Premium — 23
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A23:J23"})
    ops.append({"type": "format", "range": "A23:J23", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 23, "height": 26})'''

if old_format in src:
    src = src.replace(old_format, new_format)
    print("[OK] format_money: номера строк сдвинуты (9/10/11-14/16/17-21/23)")
else:
    print("[?] Не нашёл блок ПО МЕСЯЦАМ в format_money")

# 3. Цвет маржи — сдвигаем с G5:G15 на G5:G14
src = src.replace(
    'vals = ws.get("G5:G15")',
    'vals = ws.get("G5:G14")'
)

# 4. Цвет выводов — с 18-22 на 17-21, с B на B
src = src.replace(
    '''    # Цвет выводов 18-22
    try:
        vals = ws.get("B18:B22")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 18 + i''',
    '''    # Цвет выводов 17-21
    try:
        vals = ws.get("B17:B21")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 17 + i'''
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово.")
