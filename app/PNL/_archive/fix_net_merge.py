"""
fix_net_merge.py — старый merge от прошлой версии перекрывает B12.
Добавляем явный unmerge перед записью.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# В начало format_capital — расширить unmerge
old = '''def format_capital(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})'''

new = '''def format_capital(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})
    # Явные unmerge для проблемных зон
    for r in [4, 5, 10, 11, 12, 14, 15, 20, 22, 23, 30, 31, 37]:
        ops.append({"type": "unmerge", "range": f"A{r}:E{r}"})
        ops.append({"type": "unmerge", "range": f"A{r}:Z{r}"})
        ops.append({"type": "unmerge", "range": f"A{r}:C{r}"})'''

if old in src:
    src = src.replace(old, new)
    print("[OK] format_capital: явный unmerge для строк 4-37")
else:
    print("[?] Не нашёл начало format_capital")

# Также в самом начале пишем пустые строки, чтобы стереть старые merge
# (clear_and_write уже делает ws.clear() — но merge сохраняются)
# Это нормально, unmerge выше справится

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("Готово. Запускай: py sheets_sync.py")
