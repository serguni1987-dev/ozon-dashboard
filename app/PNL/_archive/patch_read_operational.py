"""patch_read_operational.py — read_operational читает только C:N (месяцы),
не трогая A (заголовки), B (год), O:R (кварталы) и формулы."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

OLD = '''def read_operational(ws):
    """Читает ручной ввод из строк 34-37. Возвращает dict[addr]=value."""
    saved = {}
    for r in (37, 38, 39, 40):
        try:
            row = ws.row_values(r)
            for idx, v in enumerate(row):
                if v and str(v).strip():
                    saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass
    return saved'''

NEW = '''def read_operational(ws):
    """Читает ручной ввод ТОЛЬКО из колонок C:N (месяцы) строк 37-40.
    Колонки A (заголовки), B (формула года), O:R (кварталы) НЕ трогает."""
    saved = {}
    for r in (37, 38, 39, 40):
        try:
            row = ws.row_values(r)
            # C..N = 1-based колонки 3..14 = 0-based индексы 2..13
            for idx in range(2, 14):
                if idx < len(row):
                    v = row[idx]
                    if v and str(v).strip():
                        saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass
    return saved'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] read_operational — только C:N")
else:
    print("[?] Не нашёл old read_operational — возможно, уже патчено")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] PNL/sync_pnl.py сохранён")