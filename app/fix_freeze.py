import re
src = open("sync_pnl.py", encoding="utf-8").read()

idx = src.find("def apply_format(ws, n_rows):")
end = src.find("def main():", idx)
if idx < 0 or end < 0:
    raise SystemExit("Не нашёл границы apply_format")

new_func = '''def apply_format(ws, n_rows):
    """Форматирование листа P&L: заголовок, блоки, итоги, числа, границы."""
    sid = ws.id
    reqs = []

    def grid(rng):
        m = re.match(r"([A-Z]+)(\\d+):([A-Z]+)(\\d+)", rng)
        if not m:
            m2 = re.match(r"([A-Z]+)(\\d+)", rng)
            c1, r1 = m2.group(1), m2.group(2)
            c2, r2 = c1, r1
        else:
            c1, r1, c2, r2 = m.groups()

        def col(c):
            n = 0
            for ch in c:
                n = n * 26 + (ord(ch) - ord("A") + 1)
            return n - 1

        return {"sheetId": sid,
                "startRowIndex": int(r1) - 1, "endRowIndex": int(r2),
                "startColumnIndex": col(c1), "endColumnIndex": col(c2) + 1}

    def fmt(rng, bg=None, fg=None, bold=False, italic=False,
            size=10, align=None):
        cf = {}
        if bg:
            cf["backgroundColor"] = bg
        tf = {}
        if fg:
            tf["foregroundColor"] = fg
        if bold:
            tf["bold"] = True
        if italic:
            tf["italic"] = True
        if size:
            tf["fontSize"] = size
        if tf:
            cf["textFormat"] = tf
        if align:
            cf["horizontalAlignment"] = align
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": cf},
            "fields": "userEnteredFormat"}})

    # ─── Цвета ─────────────────────────────────────────────
    NAVY   = {"red": 0.10, "green": 0.18, "blue": 0.35}
    WHITE  = {"red": 1,    "green": 1,    "blue": 1}
    BLUE   = {"red": 0.10, "green": 0.45, "blue": 0.91}   # 1A73E8
    GREY_H = {"red": 0.93, "green": 0.93, "blue": 0.93}
    GREY_T = {"red": 0.50, "green": 0.50, "blue": 0.50}
    GREEN_BG = {"red": 0.90, "green": 0.96, "blue": 0.92} # E6F4EA
    GREEN_FG = {"red": 0.07, "green": 0.45, "blue": 0.20} # 137333
    RED_BG   = {"red": 0.99, "green": 0.91, "blue": 0.90} # FCE8E6
    RED_FG   = {"red": 0.77, "green": 0.13, "blue": 0.12} # C5221F
    YEL_BG   = {"red": 1.00, "green": 0.95, "blue": 0.80} # FFF2CC
    YEL_FG   = {"red": 0.50, "green": 0.38, "blue": 0.00} # 7F6000
    NET_POS_BG = {"red": 0.85, "green": 0.92, "blue": 0.83}
    NET_NEG_BG = {"red": 0.96, "green": 0.80, "blue": 0.80}
    NET_POS_FG = {"red": 0.15, "green": 0.31, "blue": 0.07}
    NET_NEG_FG = {"red": 0.60, "green": 0.00, "blue": 0.00}
    BORDER_MED = {"red": 0.75, "green": 0.75, "blue": 0.75}

    # ─── 1. Заголовок A1:S1 ────────────────────────────────
    reqs.append({"unmergeCells": {"range": grid("A1:S1")}})
    reqs.append({"mergeCells": {"range": grid("A1:S1"),
                                "mergeType": "MERGE_ALL"}})
    fmt("A1:S1", bg=BLUE, fg=WHITE, bold=True, size=16, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 45}, "fields": "pixelSize"}})

    # ─── 2. Шапка колонок (строка 2) ───────────────────────
    fmt("A2:S2", bg=GREY_H, fg=NAVY, bold=True, size=11, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 32}, "fields": "pixelSize"}})

    # ─── 3. Справочные строки (3-6) ────────────────────────
    for r in (3, 4, 5, 6):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=10)

    # ─── 4. ДОХОДЫ (8) + подстроки (9-12) ──────────────────
    fmt("A8:S8",  bg=GREEN_BG, fg=GREEN_FG, bold=True, size=11)
    for r in (9, 10, 11, 12):
        fmt(f"A{r}:S{r}", size=10)

    # ─── 5. ПРЯМЫЕ РАСХОДЫ (14) + подстроки (15-27) ────────
    fmt("A14:S14", bg=RED_BG, fg=RED_FG, bold=True, size=11)
    SUB_SUB = {17, 18, 19, 20, 22, 23}          # логистика, отзывы и пр.
    for r in range(15, 28):
        if r in SUB_SUB:
            fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=9)
        else:
            fmt(f"A{r}:S{r}", size=10)

    # ─── 6. Себестоимость (29) ─────────────────────────────
    fmt("A29:S29", fg=RED_FG, bold=True, size=10)

    # ─── 7. ВАЛОВАЯ ПРИБЫЛЬ (31) ───────────────────────────
    fmt("A31:S31", bg=YEL_BG, fg=YEL_FG, bold=True, size=11)

    # ─── 8. ОПЕРАЦИОННЫЕ (33-37) ───────────────────────────
    fmt("A33:S33", bg=GREY_H, fg=NAVY, bold=True, size=11)
    for r in range(34, 38):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=9)

    # ─── 9. EBITDA (39) ────────────────────────────────────
    fmt("A39:S39", bg=YEL_BG, fg=YEL_FG, bold=True, size=11)

    # ─── 10. Налоги (41) ───────────────────────────────────
    fmt("A41:S41", fg=RED_FG, bold=True, size=10)

    # ─── 11. ЧИСТАЯ ПРИБЫЛЬ (43) — по знаку B43 ────────────
    net_val = 0.0
    try:
        cell = ws.acell("B43").value
        if cell:
            net_val = float(str(cell).replace(" ", "").replace(",", "."))
    except Exception:
        pass
    if net_val >= 0:
        fmt("A43:S43", bg=NET_POS_BG, fg=NET_POS_FG, bold=True, size=13)
    else:
        fmt("A43:S43", bg=NET_NEG_BG, fg=NET_NEG_FG, bold=True, size=13)

    # ─── 12. ROI и хвост (44-47) ───────────────────────────
    for r in range(44, 48):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=10)

    # ─── 13. Выравнивание ──────────────────────────────────
    for r in range(3, n_rows + 1):
        fmt(f"A{r}", align="LEFT")
        fmt(f"B{r}:S{r}", align="RIGHT")

    # ─── 14. Number format ─────────────────────────────────
    RUB = \'#,##0.00" ₽";[Red]-#,##0.00" ₽"\'
    PCT = \'0.00"\u00a0%"\'
    reqs.append({"repeatCell": {
        "range": grid(f"B3:S{n_rows}"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": RUB}}},
        "fields": "userEnteredFormat.numberFormat"}})
    # ROI — проценты
    reqs.append({"repeatCell": {
        "range": grid("B44:S44"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": PCT}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # ─── 15. Ширины ────────────────────────────────────────
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 340}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 130}, "fields": "pixelSize"}})
    for i in range(2, 19):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": 95}, "fields": "pixelSize"}})

    # ─── 16. Заморозка — ТОЛЬКО строки (без колонок) ───────
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount"}})

    # ─── 17. Границы ───────────────────────────────────────
    reqs.append({"updateBorders": {
        "range": grid("A1:S1"),
        "bottom": {"style": "SOLID_THICK", "color": BLUE}}})
    for rng in ("A8:S8", "A14:S14", "A33:S33"):
        reqs.append({"updateBorders": {
            "range": grid(rng),
            "top":    {"style": "SOLID", "color": BORDER_MED},
            "bottom": {"style": "SOLID", "color": BORDER_MED}}})
    for rng in ("A31:S31", "A39:S39", "A43:S43"):
        reqs.append({"updateBorders": {
            "range": grid(rng),
            "top":    {"style": "SOLID_THICK", "color": NAVY},
            "bottom": {"style": "SOLID",       "color": BORDER_MED}}})

    ws.spreadsheet.batch_update({"requests": reqs})


'''

src = src[:idx] + new_func + src[end:]
open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] apply_format заменён, freeze-ошибка исправлена")
