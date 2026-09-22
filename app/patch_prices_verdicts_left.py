"""
patch_prices_verdicts_left.py — смещаем выводы в B:K, чтобы не обрезались.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. В build_prices — выводы пишем в B (A пусто) ===
old = '''    data.append([v1, "", "", "", "", "", "", "", "", "", ""])
    data.append([v2, "", "", "", "", "", "", "", "", "", ""])
    data.append([v3, "", "", "", "", "", "", "", "", "", ""])
    data.append([v4, "", "", "", "", "", "", "", "", "", ""])
    if v5:
        data.append([v5, "", "", "", "", "", "", "", "", "", ""])
    data.append([v6, "", "", "", "", "", "", "", "", "", ""])'''

new = '''    data.append(["", v1, "", "", "", "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", "", "", "", ""])
    data.append(["", v4, "", "", "", "", "", "", "", "", ""])
    if v5:
        data.append(["", v5, "", "", "", "", "", "", "", "", ""])
    data.append(["", v6, "", "", "", "", "", "", "", "", ""])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_prices: выводы в колонке B")
else:
    print("[?] Не нашёл блок с выводами")

# === 2. format_prices — merge B:K вместо A:K, и заголовок тоже ===
old_hdr = '''    verdicts_start = table_start + len(items) + 2  # +1 пустая, +1 заголовок
    ops.append({"type": "merge", "range": f"A{verdicts_start}:K{verdicts_start}"})
    ops.append({"type": "format", "range": f"A{verdicts_start}:K{verdicts_start}",
                "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": verdicts_start, "height": 26})

    for i in range(n_verdicts):
        r = verdicts_start + 1 + i
        ops.append({"type": "merge", "range": f"A{r}:K{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})'''

new_hdr = '''    verdicts_start = table_start + len(items) + 2
    # Заголовок ВЫВОДЫ — в B:K (A свободна)
    ops.append({"type": "merge", "range": f"B{verdicts_start}:K{verdicts_start}"})
    ops.append({"type": "format", "range": f"B{verdicts_start}:K{verdicts_start}",
                "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": verdicts_start, "height": 26})

    for i in range(n_verdicts):
        r = verdicts_start + 1 + i
        ops.append({"type": "merge", "range": f"B{r}:K{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})'''

if old_hdr in src:
    src = src.replace(old_hdr, new_hdr)
    print("[OK] merge B:K вместо A:K")
else:
    print("[?] Не нашёл блок merge выводов")

# === 3. Форматирование выводов — B:K, а не A:K ===
old_fmt = '''        vals = ws.get(f"A{verdicts_start + 1}:A{verdicts_start + n_verdicts}")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = verdicts_start + 1 + i'''

new_fmt = '''        vals = ws.get(f"B{verdicts_start + 1}:B{verdicts_start + n_verdicts}")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = verdicts_start + 1 + i'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] чтение выводов из B")

# И применение формата B:K
src = src.replace(
    'ops2.append({"type": "format", "range": f"A{r}:K{r}", "format": CellFormat(',
    'ops2.append({"type": "format", "range": f"B{r}:K{r}", "format": CellFormat('
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
