"""patch_num_operational.py — read_operational читает ЧИСЛА (unformatted),
restore_operational пишет числа. Тогда SUM() в B37/H36 работает."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

# ── 1. read_operational — читать unformatted ──
OLD_READ = '''    for r in (37, 38, 39, 40):
        try:
            row = ws.row_values(r)
            # C..N = 1-based колонки 3..14 = 0-based индексы 2..13
            for idx in range(2, 14):
                if idx < len(row):
                    v = row[idx]
                    if v and str(v).strip():
                        saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass'''

NEW_READ = '''    for r in (37, 38, 39, 40):
        try:
            row = ws.row_values(r, value_render_option="UNFORMATTED_VALUE")
            # C..N = 1-based колонки 3..14 = 0-based индексы 2..13
            for idx in range(2, 14):
                if idx < len(row):
                    v = row[idx]
                    if v is not None and str(v).strip() not in ("", "0"):
                        saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass'''

if OLD_READ in src:
    src = src.replace(OLD_READ, NEW_READ, 1)
    print("[OK] read_operational читает UNFORMATTED_VALUE")
else:
    print("[?] Не нашёл old read_operational")

# ── 2. restore_operational — писать как число ──
OLD_RESTORE = '''    updates = [{"range": addr, "values": [[val]]} for addr, val in saved.items()]
    ws.batch_update(updates, value_input_option="USER_ENTERED")'''

NEW_RESTORE = '''    updates = []
    for addr, val in saved.items():
        # Пытаемся преобразовать в число
        try:
            num = float(str(val).replace(" ", "").replace("\\xa0", "").replace(",", "."))
            updates.append({"range": addr, "values": [[num]]})
        except (ValueError, AttributeError):
            updates.append({"range": addr, "values": [[val]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")'''

if OLD_RESTORE in src:
    src = src.replace(OLD_RESTORE, NEW_RESTORE, 1)
    print("[OK] restore_operational пишет числа")
else:
    print("[?] Не нашёл old restore_operational")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] PNL/sync_pnl.py сохранён")