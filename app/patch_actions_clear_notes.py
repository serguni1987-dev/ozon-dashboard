"""
patch_actions_clear_notes.py — очищает все примечания на листе ДЕЛАЙ,
потом ставит только нужные.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Добавляем тип "clear_notes" в batch_apply
old = '''        elif t == "filter":'''
new = '''        elif t == "clear_notes":
            # Очищает примечания во всём диапазоне
            requests.append({
                "updateCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "fields": "note",
                }
            })
        elif t == "filter":'''

if old in src and "clear_notes" not in src:
    src = src.replace(old, new, 1)
    print("[OK] тип 'clear_notes' добавлен в batch_apply")
else:
    print("[i] clear_notes уже есть")

# 2. В format_actions — первым делом очищаем все примечания
old2 = '''    # Сброс старых merge + фильтра
    ops.append({"type": "unmerge", "range": "A1:Z200"})'''

new2 = '''    # Сброс старых merge + фильтра + примечаний
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    ops.append({"type": "clear_notes", "range": "A1:Z200"})'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] clear_notes добавлен в начало format_actions")
else:
    print("[?] Не нашёл начало format_actions")

# 3. Убираем старые примечания F4, F10, G10 (могли быть в коде)
# Оставляем только F{table_hdr} и G{table_hdr}
src = src.replace(
    '''    ops.append({"type": "note", "cell": "F4",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": "G4",
                "note": "Напиши \'да\' в строке — py run.py подхватит и добавит в дневник решений."})''',
    ''
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
