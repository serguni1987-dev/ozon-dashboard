"""
patch_actions_layout.py — исправляет верстку листа ДЕЛАЙ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. build_actions — сдвигаем сводку в B/C/D (пустая A) ===
old = '''    data.append(["Категория", "SKU", "Эффект ₽/мес"])
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp_effect = sum(g["effect"] for g in cats[cat])
            data.append([cat, len(cats[cat]), f"{grp_effect:,.0f}"])
    data.append([])'''

new = '''    # Сводка — пустая A, данные в B/C/D
    data.append(["", "Категория", "SKU", "Эффект ₽/мес"])
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp_effect = sum(g["effect"] for g in cats[cat])
            data.append(["", cat, len(cats[cat]), f"{grp_effect:,.0f}"])
    data.append([])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_actions — сводка сдвинута в B/C/D")
else:
    print("[?] Не нашёл build_actions сводку")

# === 2. format_actions — заголовок сводки и строки сдвигаем на B/C/D ===
old2 = '''    # Заголовок сводки (строка 4)
    hdr = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:C4", "format": hdr})

    # Строки 5-9: категории с цветами
    row = 5
    for cat in order:
        if cat not in cats:
            continue
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        fmt_cat = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"A{row}:C{row}", "format": fmt_cat})
        ops.append({"type": "row_height", "row": row, "height": 28})
        row += 1'''

new2 = '''    # Заголовок сводки (строка 4)
    hdr = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B4:D4", "format": hdr})
    ops.append({"type": "row_height", "row": 4, "height": 28})

    # Строки 5-9: категории с цветами (в B/C/D)
    row = 5
    for cat in order:
        if cat not in cats:
            continue
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        fmt_cat_name = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        )
        fmt_cat_num = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        # B — название категории, C — SKU, D — эффект
        ops.append({"type": "format", "range": f"B{row}", "format": fmt_cat_name})
        ops.append({"type": "format", "range": f"C{row}", "format": fmt_cat_num})
        ops.append({"type": "format", "range": f"D{row}", "format": fmt_cat_num})
        ops.append({"type": "row_height", "row": row, "height": 28})
        row += 1'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] format_actions — сводка в B/C/D + высота")
else:
    print("[?] Не нашёл format_actions сводку")

# === 3. Ширины колонок — реалистичные ===
old3 = '''    ops.append({"type": "width", "col": "A", "width": 50})    # #
    ops.append({"type": "width", "col": "B", "width": 140})   # Категория
    ops.append({"type": "width", "col": "C", "width": 140})   # Offer ID
    ops.append({"type": "width", "col": "D", "width": 320})   # Название
    ops.append({"type": "width", "col": "E", "width": 380})   # Что делать
    ops.append({"type": "width", "col": "F", "width": 140})   # Эффект
    ops.append({"type": "width", "col": "G", "width": 110})   # Сделано?'''

new3 = '''    ops.append({"type": "width", "col": "A", "width": 60})    # # / пусто
    ops.append({"type": "width", "col": "B", "width": 180})   # Категория
    ops.append({"type": "width", "col": "C", "width": 170})   # SKU / Offer ID
    ops.append({"type": "width", "col": "D", "width": 320})   # Название / Эффект сводки
    ops.append({"type": "width", "col": "E", "width": 400})   # Что делать
    ops.append({"type": "width", "col": "F", "width": 140})   # Эффект
    ops.append({"type": "width", "col": "G", "width": 120})   # Сделано?'''

if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] ширины колонок обновлены")
else:
    print("[?] Не нашёл ширины колонок")

# === 4. Заголовок таблицы — тот же синий, но чуть компактнее ===
# (синий уже используется, оставим)

# === 5. Заголовок A1:G1 и подзаголовок A2:G2 — растянем до G, как и было ===
# Всё ок, уже настроено

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
