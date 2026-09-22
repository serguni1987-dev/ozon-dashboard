src = open("sheets_sync.py", encoding="utf-8").read()

# Расширяем колонку B (Название) с 180 до 420
src = src.replace(
    'ops.append({"type": "width", "col": "B", "width": 180})',
    'ops.append({"type": "width", "col": "B", "width": 420})'
)

# И колонку A чуть шире — тоже для названий
src = src.replace(
    'ops.append({"type": "width", "col": "A", "width": 260})',
    'ops.append({"type": "width", "col": "A", "width": 200})'
)

# Для синей полосы заголовка — растянем merge до I (чтобы полоса дошла до края)
src = src.replace(
    'ops.append({"type": "merge", "range": "A1:H1"})',
    'ops.append({"type": "merge", "range": "A1:M1"})'
)
src = src.replace(
    'ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})',
    'ops.append({"type": "format", "range": "A1:M1", "format": FMT_TITLE})'
)

# Остальные заголовки — до I, чтобы визуально совпадали
for old_r in ["A6:H6", "A13:H13", "A22:H22", "A11:H11", "A4:H4"]:
    src = src.replace(f'"range": "{old_r}"', f'"range": "{old_r.replace("H", "M")}"')

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] Колонки A/B расширены, заголовки до M")
