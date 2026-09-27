src = open("sheets_sync.py", encoding="utf-8").read()

# В build_frozen — итоги пишем проще: A, B, C без merge
old = '''    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", len(items), "", "", "", "", "", ""],
        ["Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽",
         f"({dead_money / total_frozen * 100:.0f}%)" if total_frozen else "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],'''

new = '''    dead_pct = f"({dead_money / total_frozen * 100:.0f}% заморозки)" if total_frozen else ""
    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", f"{len(items)}", "", "", "", "", "", ""],
        ["Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽", dead_pct, "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_frozen: итоги с явными значениями")
else:
    print("[?] Не нашёл блок итогов в build_frozen")

# В format_frozen — итоги пишем в A, B, C без merge
old_fmt = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 30})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})'''

new_fmt = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 30})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})
    # Объединяем A:B для подписи, C:D для значения, E:H для пояснения
    for r in range(5, 8):
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "merge", "range": f"C{r}:D{r}"})
        ops.append({"type": "merge", "range": f"E{r}:H{r}"})'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] format_frozen: merge A:B + C:D + E:H")
else:
    print("[?] Не нашёл блок форматирования итогов")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
