src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. В build_frozen — добавляем выводы после итогов ============
old = '''    dead_pct = f"({dead_money / total_frozen * 100:.0f}% заморозки)" if total_frozen else ""
    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", "", f"{len(items)}", "", "", "", "", ""],
        ["Всего заморожено", "", f"{total_frozen:,.0f} ₽", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", "", f"{len(dead)} SKU = {dead_money:,.0f} ₽", dead_pct, "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""],
        ["#", "Offer ID", "Название", "Ост", "Себест", "Замор", "Дней", "Индекс"],
    ]'''

new = '''    dead_pct = f"({dead_money / total_frozen * 100:.0f}% заморозки)" if total_frozen else ""

    # === Расчёт тезисов для выводов ===
    dead_count = len(dead)
    dead_pct_num = (dead_money / total_frozen * 100) if total_frozen else 0
    slow = [i for i in items if 30 < i["days_to_sell"] < 999]
    slow_money = sum(i["frozen"] for i in slow)
    fast = [i for i in items if i["days_to_sell"] <= 30]
    fast_money = sum(i["frozen"] for i in fast)
    infinite = [i for i in items if i["days_to_sell"] == 999]
    big_frozen = [i for i in items if i["frozen"] >= 5000]

    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", "", f"{len(items)}", "", "", "", "", ""],
        ["Всего заморожено", "", f"{total_frozen:,.0f} ₽", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", "", f"{len(dead)} SKU = {dead_money:,.0f} ₽", dead_pct, "", "", "", ""],
        ["", "", "", "", "", "", "", ""],

        # === ВЫВОДЫ ===
        ["ВЫВОДЫ", "", "", "", "", "", "", ""],
    ]

    if dead_pct_num > 50:
        v1 = f"❌ {dead_count} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct_num:.0f}%) — деньги стоят без дела"
    elif dead_pct_num > 25:
        v1 = f"⚠ {dead_count} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct_num:.0f}%) — половина склада не двигается"
    elif dead_pct_num > 0:
        v1 = f"✅ Мёртвых мало: {dead_count} SKU = {dead_money:,.0f} ₽ ({dead_pct_num:.0f}%)"
    else:
        v1 = "✅ Все SKU с остатком продаются"

    if infinite:
        v2 = f"🔴 {len(infinite)} SKU вообще не продавались — разобраться в первую очередь"
    elif slow:
        v2 = f"⏳ {len(slow)} SKU продаются медленно (>30 дней) = {slow_money:,.0f} ₽"
    else:
        v2 = "✅ Оборачиваемость в норме"

    if big_frozen:
        top3 = ", ".join(i["offer_id"] for i in big_frozen[:3])
        v3 = f"→ Крупные заморозки (≥5000 ₽): {len(big_frozen)} SKU ({top3}...) — начинать с них"
    else:
        v3 = "→ Крупных заморозок нет — работать по мелочи"

    if fast_money > 0:
        v4 = f"💰 {len(fast)} SKU продаются быстро (≤30 дней) = {fast_money:,.0f} ₽ — не трогать"
    else:
        v4 = ""

    if dead_money > 50000:
        v5 = f"→ ИТОГ: освободить {dead_money:,.0f} ₽ из мёртвых SKU — главная цель"
    elif dead_money > 0:
        v5 = f"→ ИТОГ: {dead_money:,.0f} ₽ можно освободить, начиная с топа"
    else:
        v5 = "→ ИТОГ: склад работает нормально"

    data.append(["", v1, "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", ""])
    if v4:
        data.append(["", v4, "", "", "", "", "", ""])
    data.append(["", v5, "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # === ТОП-30 ===
    data.append(["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""])
    data.append(["#", "Offer ID", "Название", "Ост", "Себест", "Замор", "Дней", "Индекс"])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_frozen: добавлены выводы")
else:
    print("[?] Не нашёл блок в build_frozen. Смотрю фрагмент:")
    idx = src.find("def build_frozen")
    if idx > 0:
        print(src[idx:idx+600])

# ============ 2. В format_frozen — сдвигаем всё вниз на 6 строк ============
# Было: ИТОГИ=4, итоги=5-7, ТОП-30=9, заголовки=10, данные 11-40
# Стало: ИТОГИ=4, итоги=5-7, ВЫВОДЫ=9, тезисы 10-14, ТОП-30=16, заголовки=17, данные 18-47

old_fmt = '''    # Заголовок ТОП-30
    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 26})

    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A10:H10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 32})'''

new_fmt = '''    # === ВЫВОДЫ (строки 9-14) ===
    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 26})

    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"B{r}:H{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # === ТОП-30 (строка 16) ===
    ops.append({"type": "merge", "range": "A16:H16"})
    ops.append({"type": "format", "range": "A16:H16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 26})

    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A17:H17", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 17, "height": 32})'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] format_frozen: ВЫВОДЫ 9-14, ТОП-30 на 16-17")
else:
    print("[?] Не нашёл блок ТОП-30 в format_frozen")

# Данные ТОП-30 — сдвигаем с 11-40 на 18-47
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

new_rows = '''    for r in range(18, 48):
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
    print("[OK] Данные ТОП-30: 18-47")

# Frozen — строки 17
src = src.replace(
    'ops.append({"type": "frozen", "rows": 10})',
    'ops.append({"type": "frozen", "rows": 17})'
)
print("[OK] Frozen: 17")

# Цвет индексов — H18:H47
src = src.replace(
    'vals = ws.get("H11:H40")',
    'vals = ws.get("H18:H47")'
)
src = src.replace(
    'ops2.append({"type": "format", "range": f"H{11+i}", "format": color_fmt[c]})',
    'ops2.append({"type": "format", "range": f"H{18+i}", "format": color_fmt[c]})'
)
print("[OK] Цвет индексов: H18-H47")

# ============ 3. Цвет выводов 10-14 ============
old_end = '''    try:
        vals = ws.get("H18:H47")
        color_fmt = {'''
new_end = '''    # Цвет выводов (10-14)
    try:
        vals_v = ws.get("B10:B14")
        ops3 = []
        for i, row in enumerate(vals_v):
            if not row:
                continue
            v = row[0]
            r = 10 + i
            if v.startswith("❌") or v.startswith("⚠") or v.startswith("🔴"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→ ИТОГ"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("→"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            elif v.startswith("⏳"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"B{r}:H{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            batch_apply(ws, sid, ops3)
            print(f"  Цвет выводов: {len(ops3)}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")

    try:
        vals = ws.get("H18:H47")
        color_fmt = {'''

if old_end in src:
    src = src.replace(old_end, new_end)
    print("[OK] Цвет выводов добавлен")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
