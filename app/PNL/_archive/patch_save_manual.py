import re
src = open("sync_pnl.py", encoding="utf-8").read()

if "def read_operational" not in src:
    FUNC = '''def read_operational(ws):
    """Читает ручной ввод из строк 34-37. Возвращает dict[addr]=value."""
    saved = {}
    for r in (34, 35, 36, 37):
        try:
            row = ws.row_values(r)
            for idx, v in enumerate(row):
                if v and str(v).strip():
                    saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass
    return saved


def restore_operational(ws, saved):
    """Возвращает ручные значения обратно в 34-37 после sync."""
    if not saved:
        print("[i] Ручных значений не найдено")
        return
    updates = [{"range": addr, "values": [[val]]} for addr, val in saved.items()]
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"[OK] Восстановлено ручных значений: {len(saved)}")


'''
    marker = "def main():"
    if marker not in src:
        raise SystemExit("Не нашёл def main()")
    src = src.replace(marker, FUNC + marker, 1)
    print("[OK] Функции добавлены")

old = 'ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")'
new = ('saved_op = read_operational(ws)\n'
       '    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")\n'
       '    restore_operational(ws, saved_op)')
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Чтение/восстановление добавлены в main()")
else:
    print("[?] Не нашёл строку ws.update. Покажи строку 607:")
    for i, line in enumerate(src.splitlines(), 1):
        if "ws.update" in line:
            print(f"  {i}: {line}")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")