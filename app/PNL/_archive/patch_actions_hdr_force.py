"""
patch_actions_hdr_force.py — явно снимает merge B3:E3 и перезаписывает заголовки.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Явный unmerge B3:E3 + соседних
old = '''    # Сброс старых merge + фильтра + примечаний
    ops.append({"type": "unmerge", "range": "A1:Z200"})'''

new = '''    # Сброс старых merge + фильтра + примечаний
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    ops.append({"type": "unmerge", "range": "B3:E3"})
    ops.append({"type": "unmerge", "range": "B2:G2"})
    ops.append({"type": "unmerge", "range": "A1:G1"})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] явные unmerge добавлены")
else:
    print("[?] Не нашёл блок unmerge")

# 2. Формат заголовков B3:D3 и E3 — раздельно, каждый с явным диапазоном
old2 = '''    # Заголовки сводки B3:E3 — раздельно
    hdr_cell = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B3:D3", "format": hdr_cell})
    ops.append({"type": "format", "range": "E3", "format": hdr_cell})'''

new2 = '''    # Заголовки сводки B3:E3 — раздельно и явно
    hdr_cell = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B3", "format": hdr_cell})
    ops.append({"type": "format", "range": "C3", "format": hdr_cell})
    ops.append({"type": "format", "range": "D3", "format": hdr_cell})
    ops.append({"type": "format", "range": "E3", "format": hdr_cell})'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] формат B3:E3 — раздельно")
else:
    print("[?] Не нашёл блок формата")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
