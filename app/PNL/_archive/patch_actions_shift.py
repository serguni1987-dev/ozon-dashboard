src = open("sheets_sync.py", encoding="utf-8").read()

# table_hdr 11 → 10
src = src.replace(
    "    table_hdr = 11\n    last_row = table_hdr + len(actions)",
    "    table_hdr = 10\n    last_row = table_hdr + len(actions)"
)
print("[OK] table_hdr 11 → 10")

# Заголовок сводки (строка 4) — на самом деле строка 3
src = src.replace(
    '    ops.append({"type": "format", "range": "B4:D4", "format": hdr})\n    ops.append({"type": "row_height", "row": 4, "height": 28})',
    '    ops.append({"type": "format", "range": "B3:D3", "format": hdr})\n    ops.append({"type": "row_height", "row": 3, "height": 28})'
)
print("[OK] заголовок сводки 4 → 3")

# Категории — 5-9 → 4-8
src = src.replace("    row_num = 5", "    row_num = 4")
print("[OK] категории 5-9 → 4-8")

# Примечания — note_row 5 → 4
src = src.replace("    note_row = 5", "    note_row = 4")
print("[OK] note_row 5 → 4")

# Подзаголовок A2:G2 — уже верно

# Примечание к B4 → B3
src = src.replace(
    '''    ops.append({"type": "note", "cell": "B4",
                "note": "Наведи на E5-E9 — что означает каждая категория."})''',
    '''    ops.append({"type": "note", "cell": "B3",
                "note": "Наведи на E4-E8 — что означает каждая категория."})'''
)
print("[OK] примечание B4 → B3")

# В подзаголовке build_actions — дата показывается, всё ок

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
