"""
patch_actions_wrap.py — перенос длинных названий в две строки.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Название — WRAP (перенос), высота 40px
src = src.replace(
    '''    body_left = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='CLIP',
    )''',
    '''    body_left = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )'''
)
print("[OK] body_left — WRAP")

# 2. Row height для строк таблицы = 40 (две строки текста)
src = src.replace(
    'ops.append({"type": "row_height", "row": data_row, "height": 30})',
    'ops.append({"type": "row_height", "row": data_row, "height": 42})'
)
print("[OK] высота строк таблицы = 42px")

# 3. Ширина D — 420 (больше для названий)
src = src.replace(
    'ops.append({"type": "width", "col": "D", "width": 320})   # Название / Эффект сводки',
    'ops.append({"type": "width", "col": "D", "width": 400})   # Название / Эффект сводки'
)
print("[OK] D = 400px")

# 4. Ширина E (Что делать) — 420
src = src.replace(
    'ops.append({"type": "width", "col": "E", "width": 400})   # Что делать',
    'ops.append({"type": "width", "col": "E", "width": 420})   # Что делать'
)
print("[OK] E = 420px")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
