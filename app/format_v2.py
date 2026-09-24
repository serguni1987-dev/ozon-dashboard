src = open("sync_pnl.py", encoding="utf-8").read()

# Полностью переписываем apply_format
idx = src.find("def apply_format(ws, n_rows):")
if idx < 0:
    print("[?] Не нашёл apply_format")
    raise SystemExit

# Конец функции — до "def main"
end = src.find("def main():", idx)
if end < 0:
    raise SystemExit("Не нашёл main")

new_func = '''def apply_format(ws, n_rows):
    """Полное форматирование листа P&L."""
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

    def fmt(rng, bg=None, fg=None, bold=False, size=10, align=None, wrap=None):
        cf = {}
        if bg:
            cf["backgroundColor"] = bg
        if fg or bold or size:
            cf["textFormat"] = {}
            if fg:
                cf["textFormat"]["foregroundColor"] = fg
            if bold:
                cf["textFormat"]["bold"] = True
            if size:
                cf["textFormat"]["fontSize"] = size
        if align:
            cf["horizontalAlignment"] = align
        if wrap:
            cf["wrapStrategy"] = wrap
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": cf},
            "fields": "userEnteredFormat"}})

    # Цвета
    DARK = {"red": 0.10, "green": 0.18, "blue": 0.35}       # тёмно-синий
    WHITE = {"red": 1, "green": 1, "blue": 1}
    BLUE_HEAD = {"red": 0.22, "green": 0.42, "blue": 0.70}   # синий заголовок
    GREEN = {"red": 0.82, "green": 0.94, "blue": 0.82}       # зелёный (прибыль)
    RED = {"red": 0.98, "green": 0.85, "blue": 0.85}         # красный (расходы)
    GREY = {"red": 0.94, "green": 0.94, "blue": 0.94}        # серый
    YELLOW = {"red": 1.0, "green": 0.97, "blue": 0.85}       # жёлтый (себестоимость)
    LIGHT_BLUE = {"red": 0.88, "green": 0.94, "blue": 1.0}   # голубой

    # 1. Заголовок A1:S1 (объединить)
    reqs.append({"unmergeCells": {"range": grid("A1:S1")}})
    reqs.append({"mergeCells": {"range": grid("A1:S1"), "mergeType": "MERGE_ALL"}})
    fmt("A1:S1", bg=DARK, fg=WHITE, bold=True, size=16, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 45}, "fields": "pixelSize"}})

    # 2. Заголовки колонок строка 2
    fmt("A2:S2", bg=BLUE_HEAD, fg=WHITE, bold=True, size=10, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 40}, "fields": "pixelSize"}})

    # 3. Разделы — зелёные/красные/серые
    # Номера строк:
    GREEN_SECTIONS = [8, 31, 39, 43]           # ДОХОДЫ, ВАЛОВАЯ, EBITDA, ЧИСТАЯ
    RED_SECTIONS = [14]                        # Прямые расходы
    YELLOW_SECTIONS = [29]                     # Себестоимость
    GREY_SECTIONS = [32, 41]                   # Операционные, Налоги

    for r in GREEN_SECTIONS:
        fmt(f"A{r}:S{r}", bg=GREEN, bold=True, size=11)
    for r in RED_SECTIONS:
        fmt(f"A{r}:S{r}", bg=RED, bold=True, size=11)
    for r in YELLOW_SECTIONS:
        fmt(f"A{r}:S{r}", bg=YELLOW, bold=True, size=11)
    for r in GREY_SECTIONS:
        fmt(f"A{r}:S{r}", bg=GREY, bold=True, size=11)

    # 4. Обычные строки — выравнивание
    special = set(GREEN_SECTIONS + RED_SECTIONS + YELLOW_SECTIONS + GREY_SECTIONS)
    for r in range(3, n_rows + 1):
        if r in special:
            # Разделы — тоже выравниваем значения вправо
            fmt(f"B{r}:S{r}", align="RIGHT")
            fmt(f"A{r}", align="LEFT", bold=True)
            continue
        fmt(f"A{r}", align="LEFT", size=10)
        fmt(f"B{r}:N{r}", align="RIGHT", size=10)
        fmt(f"O{r}:R{r}", align="RIGHT", size=10)

    # 5. Колонка B (Год) — светло-голубой фон
    for r in range(3, n_rows + 1):
        fmt(f"B{r}", bg=LIGHT_BLUE, align="RIGHT", size=10, bold=False)

    # 6. Кварталы O:R — серый фон
    for r in range(3, n_rows + 1):
        fmt(f"O{r}:R{r}", bg=GREY, align="RIGHT", size=10, bold=False)

    # 7. Ширины
    # A — 320px, B — 140px, C-N — 100px, O-R — 100px
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 320}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 140}, "fields": "pixelSize"}})
    for i in range(2, 18):  # C..R
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": 100}, "fields": "pixelSize"}})

    # 8. Заморозка: строки 1-2 и колонка A
    reqs.append({"updateSheetProperties": {
        "properties": {
            "sheetId": sid,
            "gridProperties": {
                "frozenRowCount": 2,
                "frozenColumnCount": 1,
            },
        },
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})

    ws.spreadsheet.batch_update({"requests": reqs})


'''

src = src[:idx] + new_func + src[end:]
open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] apply_format полностью переписан")
