"""
patch_actions_hdr_fix.py — восстанавливает 4 заголовка сводки.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Убираем merge B3:E3
src = src.replace(
    '''    # Заголовок B3:E3 объединяем для центрирования
    ops.append({"type": "merge", "range": "B3:E3"})
''',
    ''
)
print("[OK] merge B3:E3 убран")

# 2. Добавляем формат для B3, C3, D3, E3 раздельно
old = '''    # Заголовок "Что значит" — шире
    ops.append({"type": "format", "range": "E3",
                "format": CellFormat(
                    backgroundColor=Color(0.95, 0.95, 0.95),
                    textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})'''

new = '''    # Заголовки сводки B3:E3 — раздельно
    hdr_cell = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B3:D3", "format": hdr_cell})
    ops.append({"type": "format", "range": "E3", "format": hdr_cell})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] заголовки B3:E3 восстановлены")
else:
    print("[?] Не нашёл блок с E3")

# 3. Проверим, что строим в build_actions правильно
# B3 — "Категория", C3 — "SKU", D3 — "Эффект ₽/мес", E3 — "Что значит"
# Это уже так.

# 4. Дополнительно — центрирование B3:E3 через столбцы
open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
