src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Выводы: высота 50 + вертикальное CENTER + TOP отмена
old1 = '''    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"B{r}:H{r}"})
        ops.append({"type": "row_height", "row": r, "height": 45})'''
new1 = '''    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"B{r}:H{r}"})
        ops.append({"type": "row_height", "row": r, "height": 50})'''
if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] Выводы: 50px")

# 2. В build_frozen — заголовок ТОП-30 в колонке B, чтобы не срезался об A
old2 = 'data.append(["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""])'
new2 = 'data.append(["", "ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", ""])'
if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Заголовок ТОП-30 в колонке B")

# 3. Заголовок ИТОГИ тоже в B (симметрия)
old3 = '["ИТОГИ", "", "", "", "", "", "", ""],'
new3 = '["", "ИТОГИ", "", "", "", "", "", ""],'
if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Заголовок ИТОГИ в колонке B")

# 4. Заголовок ВЫВОДЫ тоже в B
old4 = '["ВЫВОДЫ", "", "", "", "", "", "", ""],'
new4 = '["", "ВЫВОДЫ", "", "", "", "", "", ""],'
if old4 in src:
    src = src.replace(old4, new4)
    print("[OK] Заголовок ВЫВОДЫ в колонке B")

# 5. merge для заголовков: A9:H9 → B9:H9, A16:H16 → B16:H16, A4:H4 → B4:H4
src = src.replace('"range": "A4:H4"', '"range": "B4:H4"')
src = src.replace('"range": "A9:H9"', '"range": "B9:H9"')
src = src.replace('"range": "A16:H16"', '"range": "B16:H16"')
print("[OK] Заголовки сдвинуты в B:H")

# 6. Выводы из B10 в C10 (первая колонка пустая для отступа)
# Нет — оставим B10, но пересоздадим точнее: merge C10:H14
# В build_frozen выводы идут в data.append(["", v1, "", ...]) — то есть в колонку B
# Оставляем

# 7. Данные ТОП-30 — заголовки в строке 17 теперь A17:H17 (уже так)
# Проверяем: таблица в 17 строке

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
