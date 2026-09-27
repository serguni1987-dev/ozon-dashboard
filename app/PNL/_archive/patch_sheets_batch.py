"""
patch_sheets_batch.py — батчит все запросы форматирования в один.
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# 1. Добавляем хелперы для конвертации в raw API-запросы
# (после определения set_note)
helper_code = '''

# ============ BATCH HELPERS ============
def _a1_to_grid_range(rng, sheet_id):
    """'A1:E1' → {'sheetId': ..., 'startRowIndex': 0, ...} (0-indexed, end-exclusive)."""
    m = re.match(r"([A-Z]+)(\\d+):([A-Z]+)(\\d+)", rng)
    if m:
        c1, r1, c2, r2 = m.groups()
    else:
        m = re.match(r"([A-Z]+)(\\d+)", rng)
        c1, r1 = m.groups()
        c2, r2 = c1, r1

    def col_idx(c):
        n = 0
        for ch in c:
            n = n * 26 + (ord(ch) - ord("A") + 1)
        return n - 1

    return {
        "sheetId": sheet_id,
        "startRowIndex": int(r1) - 1,
        "endRowIndex": int(r2),
        "startColumnIndex": col_idx(c1),
        "endColumnIndex": col_idx(c2) + 1,
    }


def _color_dict(c):
    if c is None:
        return None
    return {
        "red": c.red, "green": c.green, "blue": c.blue,
        "alpha": getattr(c, "alpha", 1.0) or 1.0,
    }


def _text_format_dict(tf):
    if tf is None:
        return None
    d = {}
    if getattr(tf, "bold", None) is not None:
        d["bold"] = tf.bold
    if getattr(tf, "italic", None) is not None:
        d["italic"] = tf.italic
    if getattr(tf, "fontSize", None) is not None:
        d["fontSize"] = tf.fontSize
    if getattr(tf, "foregroundColor", None) is not None:
        d["foregroundColor"] = _color_dict(tf.foregroundColor)
    return d or None


def _cell_format_dict(cf):
    if cf is None:
        return {}
    d = {}
    if getattr(cf, "backgroundColor", None) is not None:
        d["backgroundColor"] = _color_dict(cf.backgroundColor)
    if getattr(cf, "textFormat", None) is not None:
        tf = _text_format_dict(cf.textFormat)
        if tf:
            d["textFormat"] = tf
    for attr in ("horizontalAlignment", "verticalAlignment", "wrapStrategy"):
        v = getattr(cf, attr, None)
        if v is not None:
            d[attr] = v
    return d


def batch_apply(ws, sheet_id, operations):
    """
    operations: list of dicts:
      {"type": "format", "range": "A1:B1", "format": CellFormat}
      {"type": "width", "col": "A", "width": 200}
      {"type": "frozen", "rows": 1}
      {"type": "note", "cell": "A1", "note": "text"}
    """
    requests = []
    for op in operations:
        t = op["type"]
        if t == "format":
            fmt = _cell_format_dict(op["format"])
            requests.append({
                "repeatCell": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "cell": {"userEnteredFormat": fmt},
                    "fields": "userEnteredFormat",
                }
            })
        elif t == "width":
            col = op["col"]
            n = 0
            for ch in col:
                n = n * 26 + (ord(ch) - ord("A") + 1)
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": n - 1,
                        "endIndex": n,
                    },
                    "properties": {"pixelSize": op["width"]},
                    "fields": "pixelSize",
                }
            })
        elif t == "frozen":
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": op["rows"]},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            })
        elif t == "note":
            requests.append({
                "updateCells": {
                    "range": _a1_to_grid_range(op["cell"], sheet_id),
                    "rows": [{"values": [{"note": op["note"]}]}],
                    "fields": "note",
                }
            })

    if requests:
        ws.spreadsheet.batch_update({"requests": requests})
        return len(requests)
    return 0

'''

# Вставляем helper_code после функции set_note
anchor = "def set_note(ws, cell, note):\n    try:\n        ws.update_note(cell, note)\n    except Exception:\n        pass\n"
if anchor in src and "def batch_apply" not in src:
    src = src.replace(anchor, anchor + helper_code)
    print("[OK] Хелперы batch добавлены")
else:
    print("[?] Не нашёл место для хелперов")

# 2. Полностью переписываем format_today на batch-версию
new_format = '''def format_today(ws, values, max_date, verdict):
    sid = ws.id
    ops = []

    # A1:E1 — заголовок
    safe_unmerge(ws, "A1:E1")
    safe_merge(ws, "A1:E1")
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})

    # A2 — обновлено
    ops.append({"type": "format", "range": "A2", "format": FMT_UPDATED})

    # A4:B4 — статус свежести
    safe_unmerge(ws, "A4:B4")
    safe_merge(ws, "A4:B4")
    ops.append({"type": "format", "range": "A4:B4", "format": FMT_STATUS})

    # A6:E6 — подзаголовок + заголовки колонок
    safe_unmerge(ws, "A6:E6")
    safe_merge(ws, "A6:E6")
    ops.append({"type": "format", "range": "A6:E6", "format": FMT_SUBHEADER})
    ops.append({"type": "format", "range": "A7:E7", "format": FMT_COLHEADER})

    # Метрики
    for r in (8, 9, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": FMT_LABEL})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": FMT_VALUE})
        ops.append({"type": "format", "range": f"E{r}", "format": FMT_HINT})
    ops.append({"type": "format", "range": "B10", "format": FMT_VALUE_SMALL})

    # Δ-столбец
    def delta_fmt(text):
        s = str(text).strip()
        if s.startswith("+"):
            return FMT_DELTA_GOOD
        if s.startswith("-"):
            return FMT_DELTA_BAD
        return FMT_DELTA_BASE

    ops.append({"type": "format", "range": "D8", "format": delta_fmt(values[7][3])})
    ops.append({"type": "format", "range": "D9", "format": delta_fmt(values[8][3])})

    # Вердикт A11:E11
    safe_unmerge(ws, "A11:E11")
    safe_merge(ws, "A11:E11")
    if "✅" in verdict:
        vfmt = FMT_VERDICT_GOOD
    elif "⚠" in verdict:
        vfmt = FMT_VERDICT_BAD
    else:
        vfmt = FMT_VERDICT_NEUTRAL
    ops.append({"type": "format", "range": "A11:E11", "format": vfmt})

    # ТОП-5 — заголовок
    safe_unmerge(ws, "A13:E13")
    safe_merge(ws, "A13:E13")
    ops.append({"type": "format", "range": "A13:E13", "format": FMT_SUBHEADER})
    ops.append({"type": "format", "range": "A14:D14", "format": FMT_COLHEADER})

    # ТОП-5 — данные (строки 15-19)
    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True))
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=10))
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='RIGHT')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')
    for r in range(15, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": fmt_top_a})
        ops.append({"type": "format", "range": f"B{r}", "format": fmt_top_b})
        ops.append({"type": "format", "range": f"C{r}", "format": fmt_top_c})
        ops.append({"type": "format", "range": f"D{r}", "format": fmt_top_d})

    # Блок "Куда смотреть" — заголовок + содержимое
    safe_unmerge(ws, "A22:E22")
    safe_merge(ws, "A22:E22")
    ops.append({"type": "format", "range": "A22:E22", "format": FMT_SUBHEADER})
    for r in range(23, 28):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": FMT_ACTION_ITEM})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 260})
    ops.append({"type": "width", "col": "B", "width": 180})
    ops.append({"type": "width", "col": "C", "width": 140})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 380})

    # Заморозка
    ops.append({"type": "frozen", "rows": 1})

    # Заметки
    ops.append({"type": "note", "cell": "B8",
                "note": "Выручка за последний день в базе. Сравни с колонкой 'Среднее 7д'."})
    ops.append({"type": "note", "cell": "B9",
                "note": "Заказы в штуках (не в рублях). Обычно 1-3 в день."})
    ops.append({"type": "note", "cell": "B10",
                "note": "Сколько уникальных SKU продалось. 1-2 — узкий спрос, 5+ — широкий."})
    ops.append({"type": "note", "cell": "D8",
                "note": "Δ = Вчера − Среднее 7д. Зелёный: рост, красный: падение."})
    ops.append({"type": "note", "cell": "A4",
                "note": "Если данные старше 2 дней — скачай свежий .xlsx в downloads/ и запусти py run.py"})
    ops.append({"type": "note", "cell": "A22",
                "note": "Конкретные действия на сегодня. Полный список — на листе ДЕЛАЙ."})

    # Всё одним запросом
    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")
'''

# Заменяем старую format_today на новую
pattern = re.compile(r"def format_today\(ws, values, max_date, verdict\):.*?(?=\ndef sync_today)", re.DOTALL)
new_src, n = pattern.subn(new_format + "\n\n", src)

if n == 0:
    print("[FAIL] Не нашёл format_today")
else:
    open("sheets_sync.py", "w", encoding="utf-8").write(new_src)
    print("[OK] format_today переписана на batch")
    print("Запускай: py sheets_sync.py")
