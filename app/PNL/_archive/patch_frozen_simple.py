import re
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. build_frozen — переписываем блок ИТОГИ
old = '''    data = []
    # 1: заголовок
    data.append(["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""])
    # 2: подзаголовок
    data.append([f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""])
    # 3: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 4: ИТОГИ
    data.append(["ИТОГИ", "", "", "", "", "", "", ""])
    # 5-7: итоги (значение в колонке A, чтобы merge A:B не съел)
    data.append([f"SKU с остатком", len(items), "", "", "", "", "", ""])
    data.append([f"Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""])
    data.append([f"Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽",
                 f"({dead_pct:.0f}%)", "", "", "", "", ""])'''

new = '''    data = []
    # 1: заголовок
    data.append(["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""])
    # 2: подзаголовок
    data.append([f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""])
    # 3: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 4: ИТОГИ
    data.append(["ИТОГИ", "", "", "", "", "", "", ""])
    # 5-7: итоги — подпись и значение в одной строке
    data.append([f"SKU с остатком:  {len(items)}", "", "", "", "", "", "", ""])
    data.append([f"Всего заморожено:  {total_frozen:,.0f} ₽", "", "", "", "", "", "", ""])
    data.append([f"Мёртвые (0 продаж 30д):  {len(dead)} SKU = {dead_money:,.0f} ₽  ({dead_pct:.0f}%)",
                 "", "", "", "", "", "", ""])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_frozen: итоги — подпись+значение в одной строке")
else:
    print("[?] Не нашёл блок ИТОГИ. Ищу фрагмент:")
    idx = src.find("# 5-7: итоги")
    if idx > 0:
        print(src[idx:idx+400])

# 2. format_frozen — упрощаем итоги: только A, крупный шрифт
old2 = '''    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
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
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})'''

new2 = '''    # Итоги — простые строки в A, без merge
    total_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(0.1, 0.3, 0.6)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )

    for r in range(5, 8):
        ops.append({"type": "merge", "range": f"A{r}:D{r}"})
        ops.append({"type": "format", "range": f"A{r}:D{r}", "format": total_fmt})
        ops.append({"type": "row_height", "row": r, "height": 32})'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] format_frozen: итоги — merge A:D с крупным шрифтом")
else:
    print("[?] Не нашёл блок форматирования итогов")

# 3. Ширины — A=400, остальные по вкусу
old3 = '''    for c, w in [("A", 220), ("B", 220), ("C", 200), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})'''

new3 = '''    for c, w in [("A", 40), ("B", 150), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})'''

if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Ширины восстановлены (A=40, для ТОП-30)")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
