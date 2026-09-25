"""patch_read_before_clear.py — переносит read_operational ПЕРЕД ws.clear()."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

OLD = '''    ws.clear()
    saved_op = read_operational(ws)
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    restore_operational(ws, saved_op)'''

NEW = '''    saved_op = read_operational(ws)
    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    restore_operational(ws, saved_op)'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] read_operational перенесён перед clear")
elif "saved_op = read_operational(ws)\n    ws.clear()" in src:
    print("[i] Уже исправлено")
else:
    print("[?] Не нашёл блок. Проверь строки 681-684")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] PNL/sync_pnl.py сохранён")