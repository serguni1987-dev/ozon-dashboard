"""
patch_actions_name_short.py — обрезает названия до 80 символов и увеличивает высоту.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. build_actions — обрезаем названия
old = '''    data.append(["#", "Категория", "Offer ID", "Название", "Что делать", "Эффект ₽/мес", "Сделано?"])
    for i, a in enumerate(actions, 1):
        data.append([
            i, a["category"], a["offer_id"], a["name"],
            a["action"], f"{a['effect']:,.0f}", "",
        ])
    return data'''

new = '''    data.append(["#", "Категория", "Offer ID", "Название", "Что делать", "Эффект ₽/мес", "Сделано?"])
    for i, a in enumerate(actions, 1):
        name = (a["name"] or "").strip()
        if len(name) > 80:
            name = name[:77] + "..."
        action = (a["action"] or "").strip()
        if len(action) > 80:
            action = action[:77] + "..."
        data.append([
            i, a["category"], a["offer_id"], name,
            action, f"{a['effect']:,.0f}", "",
        ])
    return data'''

if old in src:
    src = src.replace(old, new)
    print("[OK] названия и действия обрезаны до 80 символов")
else:
    print("[?] Не нашёл блок build_actions таблицы")

# 2. Высота строк таблицы — 60px (влезет в 2-3 строки)
src = src.replace(
    'ops.append({"type": "row_height", "row": data_row, "height": 42})',
    'ops.append({"type": "row_height", "row": data_row, "height": 60})'
)
print("[OK] высота строк = 60px")

# 3. D — 380px, E — 400px
src = src.replace(
    'ops.append({"type": "width", "col": "D", "width": 400})   # Название / Эффект сводки',
    'ops.append({"type": "width", "col": "D", "width": 380})   # Название / Эффект сводки'
)
src = src.replace(
    'ops.append({"type": "width", "col": "E", "width": 420})   # Что делать',
    'ops.append({"type": "width", "col": "E", "width": 400})   # Что делать'
)
print("[OK] ширины D/E = 380/400")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
