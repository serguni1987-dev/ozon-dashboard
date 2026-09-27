src = open("sheets_sync.py", encoding="utf-8").read()

# build_frozen — значения переносим в C (индекс 2), а не B (индекс 1)
old = '''    dead_pct = f"({dead_money / total_frozen * 100:.0f}% заморозки)" if total_frozen else ""
    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", f"{len(items)}", "", "", "", "", "", ""],
        ["Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽", dead_pct, "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],'''

new = '''    dead_pct = f"({dead_money / total_frozen * 100:.0f}% заморозки)" if total_frozen else ""
    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", "", f"{len(items)}", "", "", "", "", ""],
        ["Всего заморожено", "", f"{total_frozen:,.0f} ₽", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", "", f"{len(dead)} SKU = {dead_money:,.0f} ₽", dead_pct, "", "", "", ""],
        ["", "", "", "", "", "", "", ""],'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_frozen: значения в колонку C")
else:
    print("[?] Не нашёл блок итогов")

# format_frozen — merge A:B для подписи, C:D для значения, E:H для пояснения
old_fmt = '''    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           backgroundColor=SUBHEADER_BG)
    big_num = CellFormat(textFormat=TextFormat(bold=True, fontSize=14,
                                                foregroundColor=Color(0.1, 0.3, 0.6)),
                         horizontalAlignment='LEFT', verticalAlignment='MIDDLE')
    note_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                 foregroundColor=MUTED_FG),
                          horizontalAlignment='LEFT', verticalAlignment='MIDDLE')'''

# Оставляем как есть, но меняем логику merge

old_loop = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 30})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})
    # Объединяем A:B для подписи, C:D для значения, E:H для пояснения
    for r in range(5, 8):
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "merge", "range": f"C{r}:D{r}"})
        ops.append({"type": "merge", "range": f"E{r}:H{r}"})'''

new_loop = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 32})
        # Подпись в A:B
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "format", "range": f"A{r}:B{r}", "format": label_fmt})
        # Значение в C:D
        ops.append({"type": "merge", "range": f"C{r}:D{r}"})
        ops.append({"type": "format", "range": f"C{r}:D{r}", "format": big_num})
        # Пояснение в E:H
        ops.append({"type": "merge", "range": f"E{r}:H{r}"})
        ops.append({"type": "format", "range": f"E{r}:H{r}", "format": note_fmt})'''

if old_loop in src:
    src = src.replace(old_loop, new_loop)
    print("[OK] format_frozen: подпись A:B, значение C:D, пояснение E:H")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
