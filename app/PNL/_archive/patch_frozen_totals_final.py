src = open("sheets_sync.py", encoding="utf-8").read()

# Убираем merge для строк 5-7 — оставляем A/B/C раздельно
old = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 32})
        ops.append({"type": "merge", "range": f"A{r}:B{r}"})
        ops.append({"type": "format", "range": f"A{r}:B{r}", "format": label_fmt})
        ops.append({"type": "merge", "range": f"C{r}:D{r}"})
        ops.append({"type": "format", "range": f"C{r}:D{r}", "format": big_num})
        ops.append({"type": "merge", "range": f"E{r}:H{r}"})
        ops.append({"type": "format", "range": f"E{r}:H{r}", "format": note_fmt})'''

new = '''    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 32})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})
        ops.append({"type": "format", "range": f"C{r}", "format": note_fmt})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Итоги: A/B/C раздельно, без merge")

# Ширины: A должна вместить "Мёртвые (0 продаж 30д)" — 220px
src = src.replace(
    '''    for c, w in [("A", 40), ("B", 150), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})''',
    '''    for c, w in [("A", 220), ("B", 220), ("C", 200), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})'''
)
print("[OK] Ширины: A=220, B=220, C=200")

# Данные ТОП-30 — сдвигаем обратно в A:H (без merge)
# Уже так

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
