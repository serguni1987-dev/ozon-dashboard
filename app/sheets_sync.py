"""
sheets_sync.py — выгрузка пульта Ozon в Google Sheets.
Лист СЕГОДНЯ: полный визуал с подсказками.
"""
import os
import re
import sqlite3
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from gspread_formatting import (
    format_cell_range, CellFormat, Color, TextFormat,
    set_column_width, set_frozen,
)

SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

# ID таблицы — из unitka.config (app\.env → PULT_SHEET_ID); строка выше остаётся запасным значением.
try:
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from unitka.config import SHEET_ID  # noqa: E402
except Exception:  # noqa: BLE001
    pass
CREDENTIALS = "credentials.json"
DB = "ozon.db"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
PREMIUM_FIXED  = 4990.0
TAX_PCT        = 0.15
AVG_CHECK      = 6285

# ============ ЦВЕТА ============
HEADER_BG    = Color(0x1A/255, 0x73/255, 0xE8/255)
HEADER_FG    = Color(1, 1, 1)
SUBHEADER_BG = Color(0xF8/255, 0xF9/255, 0xFA/255)
GOOD_BG      = Color(0xD9/255, 0xEA/255, 0xD3/255)
WARN_BG      = Color(0xFF/255, 0xF2/255, 0xCC/255)
BAD_BG       = Color(0xF4/255, 0xCC/255, 0xCC/255)
INFO_BG      = Color(0xE8/255, 0xF0/255, 0xFE/255)
GOOD_FG      = Color(0.10, 0.40, 0.10)
BAD_FG       = Color(0.60, 0.10, 0.10)
MUTED_FG     = Color(0.50, 0.50, 0.50)
COLHDR_FG    = Color(0.40, 0.40, 0.40)

# ============ ФОРМАТЫ ============
FMT_TITLE = CellFormat(
    backgroundColor=HEADER_BG,
    textFormat=TextFormat(foregroundColor=HEADER_FG, bold=True, fontSize=14),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)
FMT_UPDATED = CellFormat(
    textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
)
FMT_STATUS = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)
FMT_SUBHEADER = CellFormat(
    backgroundColor=SUBHEADER_BG,
    textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=Color(0.2, 0.2, 0.2)),
    verticalAlignment='MIDDLE', horizontalAlignment='CENTER',
)
FMT_COLHEADER = CellFormat(
    textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
    horizontalAlignment='LEFT',
)
FMT_LABEL = CellFormat(
    textFormat=TextFormat(fontSize=11, bold=True),
    horizontalAlignment='CENTER',
)
FMT_VALUE = CellFormat(
    textFormat=TextFormat(fontSize=16, bold=True),
    horizontalAlignment='CENTER',
)
FMT_VALUE_SMALL = CellFormat(
    textFormat=TextFormat(fontSize=14, bold=True),
    horizontalAlignment='CENTER',
)
FMT_HINT = CellFormat(
    textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
)
FMT_DELTA_BASE = CellFormat(
    textFormat=TextFormat(fontSize=12, bold=True),
    horizontalAlignment='CENTER',
)
FMT_DELTA_GOOD = CellFormat(
    backgroundColor=GOOD_BG,
    textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=GOOD_FG),
    horizontalAlignment='CENTER',
)
FMT_DELTA_BAD = CellFormat(
    backgroundColor=BAD_BG,
    textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=BAD_FG),
    horizontalAlignment='CENTER',
)
FMT_VERDICT_GOOD = CellFormat(
    backgroundColor=GOOD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=GOOD_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)
FMT_VERDICT_BAD = CellFormat(
    backgroundColor=BAD_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=BAD_FG),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)
FMT_VERDICT_NEUTRAL = CellFormat(
    backgroundColor=WARN_BG,
    textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.5, 0.4, 0.0)),
    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
)
FMT_ACTION_ITEM = CellFormat(
    textFormat=TextFormat(fontSize=11),
    horizontalAlignment='LEFT', wrapStrategy='WRAP',
)

# Цвета категорий (фон / текст)
CAT_COLORS = {
    "УБЫТОЧНЫЙ":  (Color(0xF4/255, 0xCC/255, 0xCC/255), Color(0.55, 0.05, 0.05)),  # красный
    "ДОСТАВКА":   (Color(0xFF/255, 0xF2/255, 0xCC/255), Color(0.60, 0.45, 0.00)),  # жёлтый
    "КАРТОЧКА":   (Color(0xFD/255, 0xE9/255, 0xD0/255), Color(0.55, 0.35, 0.05)),  # светло-оранжевый
    "КРИТ. МАРЖА":(Color(0xFC/255, 0xE5/255, 0xCD/255), Color(0.60, 0.30, 0.00)),  # оранжевый
    "МАСШТАБ":    (Color(0xD9/255, 0xEA/255, 0xD3/255), Color(0.10, 0.40, 0.10)),  # зелёный
}




def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    return gspread.authorize(creds)


def get_or_create_sheet(sh, title):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=200, cols=20)


def clear_and_write(ws, data):
    ws.clear()
    if data:
        ws.update(values=data, range_name="A1")


def safe_merge(ws, rng):
    try:
        ws.merge_cells(rng)
    except Exception:
        pass


def safe_unmerge(ws, rng):
    try:
        ws.unmerge_cells(rng)
    except Exception:
        pass


def format_delta_cell(ws, rng, text):
    s = str(text).strip()
    if s.startswith("+"):
        format_cell_range(ws, rng, FMT_DELTA_GOOD)
    elif s.startswith("-"):
        format_cell_range(ws, rng, FMT_DELTA_BAD)
    else:
        format_cell_range(ws, rng, FMT_DELTA_BASE)


def set_note(ws, cell, note):
    try:
        ws.update_note(cell, note)
    except Exception:
        pass


# ============ BATCH HELPERS ============
def _a1_to_grid_range(rng, sheet_id):
    """'A1:E1' → {'sheetId': ..., 'startRowIndex': 0, ...} (0-indexed, end-exclusive)."""
    m = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
    if m:
        c1, r1, c2, r2 = m.groups()
    else:
        m = re.match(r"([A-Z]+)(\d+)", rng)
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
        elif t == "merge":
            requests.append({
                "mergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "mergeType": op.get("mergeType", "MERGE_ALL"),
                }
            })
        elif t == "unmerge":
            requests.append({
                "unmergeCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                }
            })
        elif t == "clear_notes":
            # Очищает примечания во всём диапазоне
            requests.append({
                "updateCells": {
                    "range": _a1_to_grid_range(op["range"], sheet_id),
                    "fields": "note",
                }
            })
        elif t == "filter":
            requests.append({
                "setBasicFilter": {
                    "filter": {
                        "range": _a1_to_grid_range(op["range"], sheet_id)
                    }
                }
            })
        elif t == "row_height":
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": op["row"] - 1,
                        "endIndex": op["row"],
                    },
                    "properties": {"pixelSize": op["height"]},
                    "fields": "pixelSize",
                }
            })

    if requests:
        ws.spreadsheet.batch_update({"requests": requests})
        return len(requests)
    return 0



# ============ ЛИСТ СЕГОДНЯ ============
def build_today_values(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    week_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

    row = con.execute("""
        SELECT SUM(revenue), SUM(orders_units),
               SUM(CASE WHEN orders_units > 0 THEN 1 ELSE 0 END)
        FROM sales_daily WHERE date = ?
    """, (max_date,)).fetchone()
    rev_d = row[0] or 0
    ord_d = row[1] or 0
    sku_d = row[2] or 0

    row7 = con.execute("""
        SELECT AVG(rev), AVG(ord) FROM (
            SELECT date, SUM(revenue) AS rev, SUM(orders_units) AS ord
            FROM sales_daily WHERE date BETWEEN ? AND ?
            GROUP BY date
        )
    """, (week_ago, max_date)).fetchone()
    rev_avg = row7[0] or 0
    ord_avg = row7[1] or 0

    age = (datetime.now() - datetime.strptime(max_date, "%Y-%m-%d")).days
    age_text = f"⚠ Данные отстают на {age} дн. — пора обновить .xlsx" if age >= 2 else "✓ Данные актуальны"

    # Вердикт по дню
    if rev_avg > 0:
        ratio = rev_d / rev_avg
        if ratio >= 1.3:
            verdict = f"✅ ХОРОШИЙ ДЕНЬ — выручка в {ratio:.1f}× выше среднего"
        elif ratio <= 0.7:
            verdict = f"⚠ СЛАБЫЙ ДЕНЬ — выручка в {1/ratio:.1f}× ниже среднего"
        else:
            verdict = "➖ ОБЫЧНЫЙ ДЕНЬ — на уровне среднего"
    else:
        verdict = "— Нет данных для сравнения"

    top = con.execute("""
        SELECT p.offer_id, p.name, sd.revenue, sd.orders_units
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date = ? AND sd.revenue > 0 AND p.is_archived = 0
        ORDER BY sd.revenue DESC LIMIT 5
    """, (max_date,)).fetchall()

    # Сводка по проблемам для блока "Куда смотреть"
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    losses = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT p.sku
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
            HAVING SUM(sd.orders_units) > 0
        )
    """, (month_ago, max_date)).fetchone()[0] or 0

    # Точное число убыточных — из plan_core
    from plan_core import get_actions
    actions = get_actions(con, month_ago, max_date)
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    n_loss = len(cats.get("УБЫТОЧНЫЙ", []))
    n_deliv = len(cats.get("ДОСТАВКА", []))
    n_card = len(cats.get("КАРТОЧКА", []))
    effect = sum(a["effect"] for a in actions)

    delta_rev = rev_d - rev_avg
    delta_ord = ord_d - ord_avg

    # Собираем значения
    values = []
    values.append(["ПУЛЬТ OZON — СЕГОДНЯ", "", "", "", ""])           # 1
    values.append([f"обновлено {datetime.now().strftime('%d.%m.%Y %H:%M')}", "", "", "", ""])  # 2
    values.append(["", "", "", "", ""])                                # 3
    values.append([f"Последняя дата: {max_date}", age_text, "", "", ""])  # 4
    values.append(["", "", "", "", ""])                                # 5
    values.append(["ПОКАЗАТЕЛИ ЗА ВЧЕРА", "", "", "", ""])              # 6
    values.append(["Показатель", "Вчера", "Среднее 7д", "Δ", "Что это значит"])  # 7
    values.append(["Выручка", f"{rev_d:,.0f} ₽", f"{rev_avg:,.0f} ₽", f"{delta_rev:+,.0f}",
                   "Сколько заработали. Сравни с 7д — это норма или выброс"])    # 8
    values.append(["Заказы", f"{ord_d}", f"{ord_avg:.1f}", f"{delta_ord:+.1f}",
                   "Сколько штук купили. Больше 2 — обычно хороший день"])       # 9
    values.append(["Активных SKU", f"{sku_d}", "", "",
                   "Сколько товаров продалось. 1–2 = узкий спрос, 5+ = широкий"])  # 10
    values.append([verdict, "", "", "", ""])                             # 11
    values.append(["", "", "", "", ""])                                  # 12
    values.append(["ТОП-5 ВЧЕРА", "", "", "", ""])                       # 13
    values.append(["Offer ID", "Название", "Выручка", "Заказов", ""])    # 14
    for oid, name, rev, orders in top:
        values.append([oid, name, f"{rev:,.0f} ₽", orders, ""])

    # Добиваем пустыми до строки N
    while len(values) < 21:
        values.append(["", "", "", "", ""])

    # Блок "Куда смотреть"
    values.append(["КУДА СМОТРЕТЬ СЕЙЧАС", "", "", "", ""])             # 22
    values.append([f"• Лист ДЕЛАЙ: {len(actions)} SKU к работе, потенциал {effect:,.0f} ₽/мес",
                   "", "", "", ""])
    if n_loss > 0:
        values.append([f"• {n_loss} убыточных SKU съедают деньги — поднять цену или снять",
                       "", "", "", ""])
    if n_deliv > 0:
        values.append([f"• {n_deliv} SKU с брошенными корзинами — проверить доставку/габариты",
                       "", "", "", ""])
    if n_card > 0:
        values.append([f"• {n_card} SKU с мёртвым трафиком — переделать фото/описание",
                       "", "", "", ""])
    values.append([f"• Мёртвые: 202 SKU с 35 741 показов впустую (см. dead_skus.csv)",
                   "", "", "", ""])

    return values, max_date, verdict


def format_today(ws, values, max_date, verdict):
    sid = ws.id
    ops = []

    # Сбрасываем все merge на листе перед записью
    ops.append({"type": "unmerge", "range": "A1:Z50"})

    # Общие форматы заголовков
    fmt_hdr_left = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='LEFT',
    )
    fmt_hdr_right = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='RIGHT',
    )
    fmt_hdr_center = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER',
    )

    # A1:E1 — заголовок
    ops.append({"type": "merge", "range": "A1:M1"})
    ops.append({"type": "format", "range": "A1:M1", "format": FMT_TITLE})

    # A2 — обновлено
    ops.append({"type": "merge", "range": "A2:K2"})
    ops.append({"type": "format", "range": "A2:K2", "format": FMT_UPDATED})

    # A4:B4 — статус свежести
    ops.append({"type": "merge", "range": "A4:M4"})
    ops.append({"type": "format", "range": "A4:M4", "format": FMT_STATUS})

    # A6:E6 — подзаголовок + заголовки колонок
    ops.append({"type": "merge", "range": "A6:M6"})
    ops.append({"type": "format", "range": "A6:M6", "format": FMT_SUBHEADER})
    # Заголовки метрик: A — left, B/C — right (как значения), D — center
    ops.append({"type": "format", "range": "A7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "B7:C7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "D7", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "E7", "format": fmt_hdr_center})

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
    if "✅" in verdict:
        vfmt = FMT_VERDICT_GOOD
    elif "⚠" in verdict:
        vfmt = FMT_VERDICT_BAD
    else:
        vfmt = FMT_VERDICT_NEUTRAL
    ops.append({"type": "merge", "range": "A11:M11"})
    ops.append({"type": "format", "range": "A11:M11", "format": vfmt})

    # ТОП-5 — заголовок
    ops.append({"type": "merge", "range": "A13:M13"})
    ops.append({"type": "format", "range": "A13:M13", "format": FMT_SUBHEADER})
    ops.append({"type": "format", "range": "A14", "format": fmt_hdr_center})
    ops.append({"type": "format", "range": "B14", "format": fmt_hdr_left})
    ops.append({"type": "format", "range": "C14:D14", "format": fmt_hdr_center})

    # ТОП-5 — данные (строки 15-19)
    fmt_top_a = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_b = CellFormat(textFormat=TextFormat(fontSize=9),
                           horizontalAlignment='LEFT', wrapStrategy='WRAP')
    fmt_top_c = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                           horizontalAlignment='CENTER')
    fmt_top_d = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='CENTER')
    for r in range(15, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": fmt_top_a})
        ops.append({"type": "format", "range": f"B{r}", "format": fmt_top_b})
        ops.append({"type": "format", "range": f"C{r}", "format": fmt_top_c})
        ops.append({"type": "format", "range": f"D{r}", "format": fmt_top_d})

    # Блок "Куда смотреть" — заголовок + содержимое
    ops.append({"type": "merge", "range": "A22:M22"})
    ops.append({"type": "format", "range": "A22:M22", "format": FMT_SUBHEADER})

    # Строки 23-27: объединяем A:E и выравниваем по левому краю с переносом
    fmt_action = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER',
        verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(23, 28):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": fmt_action})
        ops.append({"type": "row_height", "row": r, "height": 36})

    # Высота строк метрик (чтобы колонка E не обрезалась)
    for r in (8, 9, 10):
        ops.append({"type": "row_height", "row": r, "height": 44})

    # Высота строки заголовков
    ops.append({"type": "row_height", "row": 1, "height": 40})
    ops.append({"type": "row_height", "row": 6, "height": 26})
    # ТОП-5 — высота строк 15-19
    for r in range(15, 20):
        ops.append({"type": "row_height", "row": r, "height": 36})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 200})
    ops.append({"type": "width", "col": "B", "width": 600})
    ops.append({"type": "width", "col": "C", "width": 140})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 320})
    ops.append({"type": "width", "col": "F", "width": 100})
    ops.append({"type": "width", "col": "G", "width": 100})
    ops.append({"type": "width", "col": "H", "width": 100})

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




# ============ ЛИСТ ИНСТРУКЦИЯ ============
def build_manual(con):
    data = [
        ["ПУЛЬТ OZON — ИНСТРУКЦИЯ", "", ""],
        ["", "", ""],
        ["🚀 ЕЖЕДНЕВНЫЙ РИТУАЛ  (5-15 минут утром)", "", ""],
        ["1.", "Скачать свежий .xlsx из ЛК Ozon", ""],
        ["", "Аналитика → Отчёты → Аналитика по товарам", ""],
        ["", "Период: последние 30 дней", ""],
        ["", "Положить в папку downloads/", ""],
        ["2.", "Включить VPN (Windscribe)", ""],
        ["", "Без VPN Google Sheets не обновится", ""],
        ["3.", "Запустить пульт", ""],
        ["", "py run.py   или двойной клик run.bat", ""],
        ["4.", "Открыть Google Sheets", ""],
        ["", "6 листов обновятся автоматически", ""],
        ["5.", "Выбрать 3 действия на сегодня", ""],
        ["", "Одно по ценам, одно по карточкам, одно по заморозке", ""],
        ["", "Отметить «да» в колонке «Сделано?» на листе ДЕЛАЙ", ""],
        ["", "", ""],
        ["📊 ЧТО ОЗНАЧАЕТ КАЖДЫЙ ЛИСТ", "", ""],
        ["СЕГОДНЯ", "Что происходит. Вердикт дня, топ-3, куда смотреть", ""],
        ["ДЕЛАЙ", "Что делать. 57 SKU, эффект в ₽/мес, отсортировано по деньгам", ""],
        ["ЦЕНЫ", "42 SKU с остатком. Индекс RED/SUPER, рекомендации ↓/↑", ""],
        ["ЗАМОРОЗКА", "Где деньги. 171k ₽ в складе, 30 мёртвых, что высвободить", ""],
        ["ДЕНЬГИ", "Сколько заработал. 7д / 30д / с 1 августа + по месяцам", ""],
        ["РЕЗУЛЬТАТ", "Динамика. Δ к прошлому запуску, автоматические выводы", ""],
        ["", "", ""],
        ["📅 ПЛАН НА МЕСЯЦ", "", ""],
        ["Неделя 1", "Цены: поднять SUPER (12 SKU), закрыть убыточные (11 SKU). Эффект: +15 500 ₽/мес", ""],
        ["Неделя 2", "Заморозка: топ-15 мёртвых SKU = 78 000 ₽. Освободить ~50 000 ₽", ""],
        ["Неделя 3", "Карточки: переделать 14 SKU (фото, описание, видео). Эффект: +18 855 ₽/мес", ""],
        ["Неделя 4", "Доставка: проверить 15 SKU с брошенными корзинами. Эффект: до 122 000 ₽/мес", ""],
        ["", "", ""],
        ["🔧 ЕСЛИ ЧТО-ТО СЛОМАЛОСЬ", "", ""],
        ["Google Sheets", "Проверь VPN. py check_google.py → должен быть Google API: 200", ""],
        ["Ошибка в run.py", "Запусти проблемный скрипт отдельно: py <название>.py", ""],
        ["Данные не идут", "Проверь downloads/ — есть ли свежий .xlsx", ""],
        ["Восстановить базу", "copy backups/ozon_<дата>.db ozon.db", ""],
        ["", "", ""],
        ["⚙️ ТЕХНИЧЕСКИЕ ДЕТАЛИ", "", ""],
        ["Папка проекта", os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ""],
        ["Главный скрипт", "run.py — утренний ритуал (11 шагов)", ""],
        ["База данных", "ozon.db — вся история продаж, цен, остатков", ""],
        ["Google Sheet ID", SHEET_ID, ""],
        ["Service Account", "ozon-bot@ozon-dashboard-509209.iam.gserviceaccount.com", ""],
        ["Ставки Ozon", "Комиссия 2,81%, Услуги 14,2%, Premium 4 990 ₽/мес", ""],
        ["Резервные копии", "backups/ — 30 последних копий ozon.db", ""],
        ["", "", ""],
        ["💡 ГЛАВНОЕ ПРАВИЛО", "", ""],
        ["", "Каждое утро: скачать .xlsx → py run.py → открыть Sheets → 3 действия → отметить «да»", ""],
        ["", "Без отметок не будет понимания, что работает. Дисциплина важнее интенсивности.", ""],
    ]
    return data


def format_manual(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    ops.append({"type": "merge", "range": "A1:C1"})
    ops.append({"type": "format", "range": "A1:C1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 44})

    section_rows = [3, 18, 26, 36, 43, 51]
    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    label_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    text_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )

    total_rows = 53
    for r in range(2, total_rows + 1):
        if r in section_rows:
            ops.append({"type": "merge", "range": f"A{r}:C{r}"})
            ops.append({"type": "format", "range": f"A{r}:C{r}", "format": section_fmt})
            ops.append({"type": "row_height", "row": r, "height": 32})
        else:
            ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
            ops.append({"type": "format", "range": f"B{r}", "format": text_fmt})
            ops.append({"type": "row_height", "row": r, "height": 26})

    ops.append({"type": "width", "col": "A", "width": 180})
    ops.append({"type": "width", "col": "B", "width": 780})
    ops.append({"type": "width", "col": "C", "width": 80})

    ops.append({"type": "frozen", "rows": 1})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")


def sync_manual(sh, con):
    print("")
    print("[Лист ИНСТРУКЦИЯ]")
    ws = get_or_create_sheet(sh, "ИНСТРУКЦИЯ")
    data = build_manual(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_manual(ws)
    # Перемещаем в начало списка вкладок через API
    try:
        sh.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "index": 0},
                "fields": "index",
            }
        }]})
        print("  Перемещён на первое место")
    except Exception as e:
        print(f"  [WARN] Не удалось переместить: {e}")


def sync_today(sh, con):
    print("\n[Лист СЕГОДНЯ]")
    ws = get_or_create_sheet(sh, "СЕГОДНЯ")
    values, max_date, verdict = build_today_values(con)
    clear_and_write(ws, values)
    print(f"  Записано строк: {len(values)}")
    format_today(ws, values, max_date, verdict)
    print(f"  Форматирование применено")
    print(f"  Вердикт: {verdict}")


# ============ ОСТАЛЬНЫЕ ЛИСТЫ ============
def build_actions(con):
    from plan_core import get_actions
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)

    data = [
        ["ПЛАН ДЕЙСТВИЙ", f"{len(actions)} SKU, потенциал {sum(a['effect'] for a in actions):,.0f} ₽/мес"],
        [],
    ]
    if not actions:
        data.append(["Действий нет."])
        return data

    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    # Сводка — A пусто, B/C/D/E — данные
    cat_short = {
        "УБЫТОЧНЫЙ":   "Каждый заказ в убыток → поднять цену или снять",
        "ДОСТАВКА":    "Корзины есть, заказов нет → проверить доставку",
        "КАРТОЧКА":    "Заходы есть, заказов нет → фото/описание",
        "КРИТ. МАРЖА": "Маржа 0-5% → поднять цену",
        "МАСШТАБ":     "Маржа 25%+ → в акции, пополнить остатки",
    }
    data.append(["", "Категория", "SKU", "Эффект ₽/мес", "Что значит"])
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp_effect = sum(g["effect"] for g in cats[cat])
            data.append(["", cat, len(cats[cat]), f"{grp_effect:,.0f}", cat_short.get(cat, "")])
    data.append([])

    data.append(["#", "Категория", "Offer ID", "Название", "Что делать", "Эффект ₽/мес", "Сделано?"])
    for i, a in enumerate(actions, 1):
        name = (a["name"] or "").strip()
        if len(name) > 80:
            name = name[:77] + "..."
        action = (a["action"] or "").strip()
        if len(action) > 80:
            action = action[:77] + "..."
        data.append([
            i, a["category"], a["offer_id"], name,
            action, f"{a['effect']:,.0f}", "",
        ])
    return data




# ============ ЛИСТ ДЕЛАЙ ============
def format_actions(ws, actions, total_effect):
    sid = ws.id
    ops = []

    # Сброс старых merge + фильтра + примечаний
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    ops.append({"type": "unmerge", "range": "B3:E3"})
    ops.append({"type": "unmerge", "range": "B2:G2"})
    ops.append({"type": "unmerge", "range": "A1:G1"})
    ops.append({"type": "clear_notes", "range": "A1:Z200"})
    # Сброс старого фильтра (если был)
    try:
        ws.spreadsheet.batch_update({"requests": [{
            "clearBasicFilter": {"sheetId": sid}
        }]})
    except Exception:
        pass

    # === Заголовок A1:G1 ===
    ops.append({"type": "merge", "range": "A1:G1"})
    ops.append({"type": "format", "range": "A1:G1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # === Подзаголовок A2:G2 ===
    subtitle_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.15, 0.15, 0.15)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:G2"})
    ops.append({"type": "format", "range": "A2:G2", "format": subtitle_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 30})

    # === Сводка: заголовок в строке 4, категории в 5-9 ===
    hdr = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B3:D3", "format": hdr})
    ops.append({"type": "row_height", "row": 3, "height": 28})

    order = ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    # Строки 5-9 — категории
    row_num = 4
    for cat in order:
        if cat not in cats:
            continue
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        fmt_cat_name = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        )
        fmt_cat_num = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"B{row_num}", "format": fmt_cat_name})
        ops.append({"type": "format", "range": f"C{row_num}", "format": fmt_cat_num})
        ops.append({"type": "format", "range": f"D{row_num}", "format": fmt_cat_num})
        ops.append({"type": "row_height", "row": row_num, "height": 28})
        row_num += 1

    # === Таблица действий: заголовки в строке 11 ===
    table_hdr = 10
    last_row = table_hdr + len(actions)

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": f"A{table_hdr}:G{table_hdr}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_hdr, "height": 36})

    # Данные таблицы
    body_center = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    body_effect = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_offer = CellFormat(
        textFormat=TextFormat(fontSize=10, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    done_cell = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=Color(0.97, 0.97, 0.97),
    )

    r = table_hdr + 1
    for a in actions:
        cat = a["category"]
        _, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        cat_cell = CellFormat(
            textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": cat_cell})
        ops.append({"type": "format", "range": f"C{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"D{r}", "format": body_left})
        ops.append({"type": "format", "range": f"E{r}", "format": body_left})
        ops.append({"type": "format", "range": f"F{r}", "format": body_effect})
        ops.append({"type": "format", "range": f"G{r}", "format": done_cell})
        ops.append({"type": "row_height", "row": r, "height": 60})
        r += 1

    # === Ширины колонок ===
    ops.append({"type": "width", "col": "A", "width": 60})
    ops.append({"type": "width", "col": "B", "width": 180})
    ops.append({"type": "width", "col": "C", "width": 170})
    ops.append({"type": "width", "col": "D", "width": 380})
    ops.append({"type": "width", "col": "E", "width": 400})
    ops.append({"type": "width", "col": "F", "width": 140})
    ops.append({"type": "width", "col": "G", "width": 120})

    # === Заморозка ===
    ops.append({"type": "frozen", "rows": table_hdr})

    # === ФИЛЬТР на таблицу действий ===
    ops.append({"type": "filter", "range": f"A{table_hdr}:G{last_row}"})

    # === Примечания на НАЗВАНИЯ категорий (B4:B8) ===
    cat_notes = {
        "УБЫТОЧНЫЙ":   "Маржа отрицательная. Каждый заказ приносит убыток. Что делать: поднять цену или снять с продажи. См. лист ДЕЛАЙ для конкретных SKU.",
        "ДОСТАВКА":    "Клиенты дошли до корзины, но не оформили заказ. Обычно — проблема доставки: габариты, сроки, ПВЗ. Проверить в ЛК Ozon брошенные корзины.",
        "КАРТОЧКА":    "Показы и заходы есть, но заказов нет. Проблема в карточке: главное фото, описание, отзывы. Переделать карточку.",
        "КРИТ. МАРЖА": "Маржа 0-5%. Работает почти в ноль. Что делать: поднять цену на 5-10%.",
        "МАСШТАБ":     "Маржа 25%+. Товар хорошо идёт. Что делать: включить в акции, бустинг, пополнить остатки.",
    }
    note_row = 4
    for cat in order:
        if cat in cats:
            # Примечание на название категории (B4:B8)
            ops.append({"type": "note", "cell": f"B{note_row}",
                        "note": cat_notes.get(cat, "")})
            note_row += 1

    # Заголовки сводки B3:E3 — раздельно и явно
    hdr_cell = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B3", "format": hdr_cell})
    ops.append({"type": "format", "range": "C3", "format": hdr_cell})
    ops.append({"type": "format", "range": "D3", "format": hdr_cell})
    ops.append({"type": "format", "range": "E3", "format": hdr_cell})
    # Строки 4-8 в колонке E — обычный текст
    for r in range(4, 9):
        ops.append({"type": "format", "range": f"E{r}",
                    "format": CellFormat(
                        textFormat=TextFormat(fontSize=9, italic=True, foregroundColor=MUTED_FG),
                        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                        wrapStrategy='WRAP',
                    )})


    # Другие примечания
    ops.append({"type": "note", "cell": "B3",
                "note": "Наведи на название категории (B4:B8) — подробное описание. Колонка E — краткая расшифровка."})
    ops.append({"type": "note", "cell": f"F{table_hdr}",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_hdr}",
                "note": "Напиши 'да' в строке — py run.py подхватит и добавит в дневник решений."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")


def sync_actions(sh, con):
    print("\n[Лист ДЕЛАЙ]")
    ws = get_or_create_sheet(sh, "ДЕЛАЙ")
    data = build_actions(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")

    # Достаём actions для форматирования
    from plan_core import get_actions
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)
    total_effect = sum(a["effect"] for a in actions)

    format_actions(ws, actions, total_effect)
    print("  Форматирование применено")









# ============ ЛИСТ ЦЕНЫ ============
def build_prices(con):
    """Лист ЦЕНЫ — только SKU с остатком > 0. Рабочий инструмент менеджера."""
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cp.offer_id, cp.price, cp.min_price, cp.price_index_color,
               p.name, p.cost_price,
               COALESCE(sd.orders, 0) AS orders_30d,
               cs.total_present AS stock
        FROM current_stocks cs
        JOIN current_prices cp ON cp.offer_id = cs.offer_id
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ?
            GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND cp.price > 0 AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        price = r["price"] or 0
        cost = r["cost_price"] or 0
        min_p = r["min_price"] or 0
        stock = r["stock"] or 0
        orders = r["orders_30d"] or 0
        color = r["price_index_color"] or "WITHOUT_INDEX"

        unit_profit = price * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
        unit_margin = unit_profit / price if price else 0

        # Рекомендация менеджеру
        if unit_profit < 0:
            recommend = "❌ Убыток — срочно поднять"
        elif color == "RED" and min_p > 0:
            target = min_p * 1.02
            new_profit = target * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
            if new_profit > 0:
                recommend = f"↓ Снизить до {target:,.0f} ₽"
            else:
                recommend = "→ Снять (маржа уйдёт в минус)"
        elif color == "SUPER" and orders > 0:
            # SUPER + продаётся = можно смело поднять 7-15%
            step = price * 1.07
            if min_p > price * 1.05:
                step = min(min_p * 1.02, price * 1.15)
            target = step
            pct = (target / price - 1) * 100
            recommend = f"↑ Поднять до {target:,.0f} ₽ (+{pct:.0f}%)"
        elif color == "SUPER" and orders == 0:
            recommend = "🔍 SUPER, но не продаётся — проверить карточку"
        elif color == "GREEN" and orders > 0:
            step = price * 1.05
            if min_p > price * 1.05:
                step = min(min_p * 1.02, price * 1.10)
            target = step
            pct = (target / price - 1) * 100
            recommend = f"↑ Поднять до {target:,.0f} ₽ (+{pct:.0f}%)"
        elif orders == 0:
            recommend = "○ Наблюдать"
        else:
            recommend = "✓ Оставить"

        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:60],
            "cost": cost,
            "price": price,
            "min_price": min_p,
            "color": color,
            "unit_profit": unit_profit,
            "unit_margin": unit_margin,
            "orders_30d": orders,
            "stock": stock,
            "recommend": recommend,
        })

    # Сортировка: сначала RED (проблема), потом SUPER (можно поднять), потом остальные
    order = {"RED": 0, "YELLOW": 1, "GREEN": 2, "SUPER": 3, "WITHOUT_INDEX": 4}
    items.sort(key=lambda x: (order.get(x["color"], 9), -x["stock"]))

    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)

    data = []
    data.append(["ЦЕНЫ — только SKU с остатком (актуально из Ozon API)",
                 "", "", "", "", "", "", ""])
    data.append([f"всего SKU с остатком: {total}  |  "
                 f"🔴 RED: {colors.get('RED', 0)}  |  "
                 f"🟡 YELLOW: {colors.get('YELLOW', 0)}  |  "
                 f"🟢 GREEN: {colors.get('GREEN', 0)}  |  "
                 f"🟣 SUPER: {colors.get('SUPER', 0)}",
                 "", "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", ""])
    red_count = colors.get("RED", 0)
    super_count = colors.get("SUPER", 0)
    loss_count = sum(1 for i in items if i["unit_profit"] < 0)

    if red_count > 0:
        v1 = f"⚠ {red_count} SKU дороже рынка — снизить цену до Min"
    else:
        v1 = "✅ Нет SKU дороже рынка"

    if super_count > 0:
        v2 = f"💰 {super_count} SKU в SUPER — можно поднять цену"
    else:
        v2 = "ℹ Нет SKU в SUPER"

    if loss_count > 0:
        v3 = f"❌ {loss_count} SKU убыточны — поднять цену или снять"
    else:
        v3 = "✅ Убыточных нет"

    data.append(["", v1, "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # Таблица
    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Ост", "Зак", "Рекомендация"])

    for it in items:
        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"
        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            it["stock"],
            it["orders_30d"],
            it["recommend"],
        ])

    return data, items, 3


def format_prices(ws, items, n_verdicts=3):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z500"})
    ops.append({"type": "clear_notes", "range": "A1:Z500"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:J1"})
    ops.append({"type": "format", "range": "A1:J1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:J2"})
    ops.append({"type": "format", "range": "A2:J2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # ВЫВОДЫ — заголовок строка 4, тезисы 5-7
    ops.append({"type": "merge", "range": "A4:J4"})
    ops.append({"type": "format", "range": "A4:J4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    for i in range(n_verdicts):
        r = 5 + i
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # Таблица — строка 9
    table_start = 9
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": f"A{table_start}:J{table_start}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_start, "height": 32})

    color_fmt = {
        "RED":          CellFormat(backgroundColor=BAD_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                   horizontalAlignment='CENTER'),
        "YELLOW":       CellFormat(backgroundColor=WARN_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                   horizontalAlignment='CENTER'),
        "GREEN":        CellFormat(backgroundColor=GOOD_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                   horizontalAlignment='CENTER'),
        "SUPER":        CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                   textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                   horizontalAlignment='CENTER'),
        "WITHOUT_INDEX":CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER'),
    }
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_price = CellFormat(textFormat=TextFormat(fontSize=11, bold=True),
                            horizontalAlignment='CENTER')

    r = table_start + 1
    for it in items:
        ops.append({"type": "format", "range": f"A{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"B{r}", "format": body_left})
        ops.append({"type": "format", "range": f"C{r}", "format": body_center})
        ops.append({"type": "format", "range": f"D{r}", "format": body_price})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": color_fmt.get(it["color"], body_center)})
        if it["unit_profit"] < 0:
            pf = CellFormat(backgroundColor=BAD_BG,
                            textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=BAD_FG),
                            horizontalAlignment='CENTER')
        else:
            pf = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
        ops.append({"type": "format", "range": f"G{r}", "format": pf})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "format", "range": f"I{r}", "format": body_center})
        ops.append({"type": "format", "range": f"J{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 26})
        r += 1

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 400})
    ops.append({"type": "width", "col": "C", "width": 80})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 60})
    ops.append({"type": "width", "col": "I", "width": 60})
    ops.append({"type": "width", "col": "J", "width": 280})

    ops.append({"type": "frozen", "rows": table_start})

    last_row = table_start + len(items)
    ops.append({"type": "filter", "range": f"A{table_start}:J{last_row}"})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цвет выводов
    try:
        vals = ws.get(f"B5:B{4 + n_verdicts}")
        ops2 = []
        for i, row_v in enumerate(vals):
            if not row_v:
                continue
            v = row_v[0]
            r = 5 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"B{r}:J{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")


def sync_prices(sh, con):
    print("\n[Лист ЦЕНЫ]")
    ws = get_or_create_sheet(sh, "ЦЕНЫ")
    data, items, n_verdicts = build_prices(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_prices(ws, items, n_verdicts)


# ============ ЛИСТ ЗАМОРОЗКА ============

def build_frozen(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cs.offer_id, cs.total_present AS stock,
               p.name, p.cost_price,
               COALESCE(sd.orders, 0) AS orders_30d,
               cp.price_index_color AS color
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN current_prices cp ON cp.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ? GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        stock = r["stock"] or 0
        cost = r["cost_price"] or 0
        frozen = stock * cost
        orders = r["orders_30d"] or 0
        days = stock / (orders / 30) if orders > 0 else 999
        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:55],
            "stock": int(stock),
            "cost": cost,
            "frozen": frozen,
            "orders_30d": orders,
            "days_to_sell": days,
            "color": r["color"] or "",
        })
    items.sort(key=lambda x: -x["frozen"])

    total_frozen = sum(i["frozen"] for i in items)
    dead = [i for i in items if i["orders_30d"] == 0]
    dead_money = sum(i["frozen"] for i in dead)
    dead_pct = (dead_money / total_frozen * 100) if total_frozen else 0
    infinite = [i for i in items if i["days_to_sell"] == 999]
    slow = [i for i in items if 30 < i["days_to_sell"] < 999]
    slow_money = sum(i["frozen"] for i in slow)
    fast = [i for i in items if i["days_to_sell"] <= 30]
    fast_money = sum(i["frozen"] for i in fast)
    big_frozen = [i for i in items if i["frozen"] >= 5000]

    # === Тезисы выводов ===
    if dead_pct > 50:
        v1 = f"❌ {len(dead)} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct:.0f}%) — деньги стоят без дела"
    elif dead_pct > 25:
        v1 = f"⚠ {len(dead)} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct:.0f}%) — половина склада не двигается"
    elif dead_money > 0:
        v1 = f"✅ Мёртвых мало: {len(dead)} SKU = {dead_money:,.0f} ₽ ({dead_pct:.0f}%)"
    else:
        v1 = "✅ Все SKU с остатком продаются"

    if infinite:
        v2 = f"🔴 {len(infinite)} SKU вообще не продавались — разобраться в первую очередь"
    elif slow:
        v2 = f"⏳ {len(slow)} SKU продаются медленно (>30 дней) = {slow_money:,.0f} ₽"
    else:
        v2 = "✅ Оборачиваемость в норме"

    if big_frozen:
        top3 = ", ".join(i["offer_id"] for i in big_frozen[:3])
        v3 = f"→ Крупные заморозки (≥5000 ₽): {len(big_frozen)} SKU ({top3}...) — начинать с них"
    else:
        v3 = "→ Крупных заморозок нет — работать по мелочи"

    if fast_money > 0:
        v4 = f"💰 {len(fast)} SKU продаются быстро (≤30 дней) = {fast_money:,.0f} ₽ — не трогать"
    else:
        v4 = ""

    if dead_money > 50000:
        v5 = f"→ ИТОГ: освободить {dead_money:,.0f} ₽ из мёртвых SKU — главная цель"
    elif dead_money > 0:
        v5 = f"→ ИТОГ: {dead_money:,.0f} ₽ можно освободить"
    else:
        v5 = "→ ИТОГ: склад работает нормально"

    # === Сборка data — все заголовки и выводы в колонке A ===
    data = []
    # 1: заголовок
    data.append(["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""])
    # 2: подзаголовок
    data.append([f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""])
    # 3: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 4: ИТОГИ
    data.append(["ИТОГИ", "", "", "", "", "", "", ""])
    # 5-7: итоги — подпись и значение в одной строке
    data.append([f"SKU с остатком:  {len(items)}", "", "", "", "", "", "", ""])
    data.append([f"Всего заморожено:  {total_frozen:,.0f} ₽", "", "", "", "", "", "", ""])
    data.append([f"Мёртвые (0 продаж 30д):  {len(dead)} SKU = {dead_money:,.0f} ₽  ({dead_pct:.0f}%)",
                 "", "", "", "", "", "", ""])
    # 8: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 9: ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", ""])
    # 10-14: 5 тезисов — все в колонке A
    data.append([v1, "", "", "", "", "", "", ""])
    data.append([v2, "", "", "", "", "", "", ""])
    data.append([v3, "", "", "", "", "", "", ""])
    data.append([v4, "", "", "", "", "", "", ""])
    data.append([v5, "", "", "", "", "", "", ""])
    # 15: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 16: ТОП-30
    data.append(["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""])
    # 17: заголовки
    data.append(["#", "Offer ID", "Название", "Ост", "Себест", "Замор", "Дней", "Индекс"])
    # 18+: данные
    for i, it in enumerate(items[:30], 1):
        days_str = f"{it['days_to_sell']:.0f}" if it['days_to_sell'] < 999 else "∞"
        data.append([i, it["offer_id"], it["name"], it["stock"],
                     f"{it['cost']:,.0f}", f"{it['frozen']:,.0f}",
                     days_str, it["color"]])

    return data, items


def format_frozen(ws, items):
    sid = ws.id
    ops = []

    # Жёсткий сброс всего
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    ops.append({"type": "clear_notes", "range": "A1:Z200"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:H1"})
    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG, horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A2:H2"})
    ops.append({"type": "format", "range": "A2:H2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # === ИТОГИ — заголовок строки 4 ===
    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": section_fmt})
    ops.append({"type": "row_height", "row": 4, "height": 28})

    # === Итоги 5-7: A:B подпись, C значение, D пояснение ===
    # Итоги — простые строки в A, без merge
    total_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=14, foregroundColor=Color(0.1, 0.3, 0.6)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )

    for r in range(5, 8):
        ops.append({"type": "merge", "range": f"A{r}:D{r}"})
        ops.append({"type": "format", "range": f"A{r}:D{r}", "format": total_fmt})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # === ВЫВОДЫ — заголовок строка 9 ===
    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": section_fmt})
    ops.append({"type": "row_height", "row": 9, "height": 28})

    # === Выводы 10-14 ===
    # Каждый в отдельной строке с merge A:H
    verdict_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP')
    for r in range(10, 15):
        ops.append({"type": "merge", "range": f"A{r}:H{r}"})
        ops.append({"type": "format", "range": f"A{r}:H{r}", "format": verdict_fmt})
        ops.append({"type": "row_height", "row": r, "height": 40})

    # === ТОП-30 — заголовок строка 16 ===
    ops.append({"type": "merge", "range": "A16:H16"})
    ops.append({"type": "format", "range": "A16:H16", "format": section_fmt})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    # Заголовки таблицы — 17
    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A17:H17", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 17, "height": 32})

    # Данные ТОП-30 — 18-47
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_money = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')

    for r in range(18, 48):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})

    # Ширины
    for c, w in [("A", 40), ("B", 150), ("C", 380), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 140)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 17})

    n = batch_apply(ws, sid, ops)
    print(f"  Основное форматирование: {n}")

    # Цвет выводов (10-14)
    try:
        vals = ws.get("A10:A14")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 10 + i
            if v.startswith("❌") or v.startswith("⚠") or v.startswith("🔴"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→ ИТОГ") or v.startswith("→"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            elif v.startswith("⏳"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"A{r}:H{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {len(ops2)}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")

    # Цвет индексов (H18:H47)
    try:
        vals = ws.get("H18:H47")
        color_fmt = {
            "RED":   CellFormat(backgroundColor=BAD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                horizontalAlignment='CENTER'),
            "SUPER": CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                horizontalAlignment='CENTER'),
            "GREEN": CellFormat(backgroundColor=GOOD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                horizontalAlignment='CENTER'),
            "YELLOW": CellFormat(backgroundColor=WARN_BG,
                                 textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                 horizontalAlignment='CENTER'),
            "WITHOUT_INDEX": CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                              foregroundColor=MUTED_FG),
                                        horizontalAlignment='CENTER'),
        }
        ops3 = []
        for i, row in enumerate(vals):
            c = (row[0] or "").strip() if row else ""
            if c in color_fmt:
                ops3.append({"type": "format", "range": f"H{18+i}", "format": color_fmt[c]})
        if ops3:
            batch_apply(ws, sid, ops3)
            print(f"  Цвет индексов: {len(ops3)}")
    except Exception as e:
        print(f"  [WARN] Цвет: {e}")


def sync_frozen(sh, con):
    print("\n[Лист ЗАМОРОЗКА]")
    ws = get_or_create_sheet(sh, "ЗАМОРОЗКА")
    data, items = build_frozen(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_frozen(ws, items)


# ============ ЛИСТ ДЕНЬГИ (упрощённый) ============



def build_money(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    periods = [
        ("7 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), max_date),
        ("30 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"), max_date),
        ("с 1 августа", "2026-08-01", max_date),
    ]

    def calc(d1, d2):
        rows = con.execute("""
            SELECT p.sku, p.cost_price,
                   SUM(sd.revenue) AS rev, SUM(sd.orders_units) AS orders
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
        """, (d1, d2)).fetchall()
        rev = cost = comm = serv = profit = 0.0
        orders = 0
        for sku, cp, r, o in rows:
            r = r or 0
            o = o or 0
            cp = cp or 0
            c = cp * o
            cm = r * COMMISSION_PCT
            sv = r * SERVICES_PCT
            pb = r - c - cm - sv
            tx = pb * TAX_PCT if pb > 0 else 0
            rev += r
            cost += c
            comm += cm
            serv += sv
            profit += pb - tx
            orders += o
        m = profit / rev if rev else 0
        avg = rev / orders if orders else 0
        return rev, cost, comm, serv, profit, m, orders, avg

    def verdict(m):
        if m < 0.05:
            return "Убыток"
        if m < 0.10:
            return "Тонко"
        if m < 0.15:
            return "Норма"
        return "Отлично"

    period_stats = {}
    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", "", ""],
        ["ставки: комиссия " + str(round(COMMISSION_PCT*100, 2)) + "%, услуги " + str(round(SERVICES_PCT*100, 1)) + "%", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon", "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"],
    ]
    for label, d1, d2 in periods:
        rev, cost, comm, serv, profit, m, orders, avg = calc(d1, d2)
        period_stats[label] = (rev, cost, comm, serv, profit, m, orders, avg)
        data.append([label, f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{m*100:.1f}%", orders,
                     f"{avg:,.0f}", verdict(m)])

    data.append(["", "", "", "", "", "", "", "", "", ""])

    # ПО МЕСЯЦАМ
    data.append(["ПО МЕСЯЦАМ", "", "", "", "", "", "", "", "", ""])
    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon", "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"])

    months = con.execute("""
        SELECT substr(date, 1, 7) AS m, MIN(date), MAX(date)
        FROM sales_daily GROUP BY m ORDER BY m DESC
    """).fetchall()
    month_stats = {}
    for m, d1, d2 in months:
        rev, cost, comm, serv, profit, mrg, orders, avg = calc(d1, d2)
        month_stats[m] = (rev, cost, comm, serv, profit, mrg, orders, avg)
        label = {"2026-06": "Июнь 2026", "2026-07": "Июль 2026", "2026-08": "Август 2026", "2026-09": "Сентябрь 2026"}.get(m, m)
        data.append([label, f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{mrg*100:.1f}%", orders,
                     f"{avg:,.0f}", verdict(mrg)])

    data.append(["", "", "", "", "", "", "", "", "", ""])

    # ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", "", "", ""])

    s30 = period_stats["30 дней"]
    margin_30 = s30[5]
    cost_pct = s30[1] / s30[0] if s30[0] else 0
    serv_pct = s30[3] / s30[0] if s30[0] else 0

    if margin_30 < 0.05:
        v1 = "Критично: маржа " + f"{margin_30*100:.1f}%" + " — работаем почти в ноль"
    elif margin_30 < 0.10:
        v1 = "Тонко: маржа " + f"{margin_30*100:.1f}%" + " — любой сбой уводит в минус"
    elif margin_30 < 0.15:
        v1 = "Норма: маржа " + f"{margin_30*100:.1f}%" + " — есть куда расти"
    else:
        v1 = "Отлично: маржа " + f"{margin_30*100:.1f}%"

    aug = month_stats.get("2026-08")
    sep = month_stats.get("2026-09")
    if aug and sep:
        d_m = (sep[5] - aug[5]) * 100
        if d_m < -1:
            v2 = "Падение маржи: сентябрь " + f"{sep[5]*100:.1f}%" + " vs август " + f"{aug[5]*100:.1f}%" + " (" + f"{d_m:+.1f}" + " п.п.) — разобраться с убыточными SKU"
        elif d_m > 1:
            v2 = "Рост маржи: " + f"{aug[5]*100:.1f}%" + " -> " + f"{sep[5]*100:.1f}%" + " (" + f"{d_m:+.1f}" + " п.п.)"
        else:
            v2 = "Маржа стабильна: " + f"{sep[5]*100:.1f}%"
    else:
        v2 = "Динамика: недостаточно данных"

    if cost_pct > 0.75:
        v3 = "Себестоимость съедает " + f"{cost_pct*100:.0f}%" + " выручки — главный рычаг роста"
    elif cost_pct > 0.65:
        v3 = "Себестоимость " + f"{cost_pct*100:.0f}%" + " — торговаться с поставщиком"
    else:
        v3 = "Себестоимость " + f"{cost_pct*100:.0f}%" + " — приемлемо"

    if serv_pct > 0.15:
        v4 = "Услуги Ozon " + f"{serv_pct*100:.1f}%" + " — проверить логистику и возвраты"
    else:
        v4 = "Услуги Ozon " + f"{serv_pct*100:.1f}%" + " — в норме"

    from plan_core import get_actions
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)
    if actions:
        top = actions[0]
        total_effect = sum(a["effect"] for a in actions)
        v5 = "Действия: " + top["offer_id"] + " (" + top["category"] + ", " + f"{top['effect']:,.0f}" + " руб), всего " + str(len(actions)) + " SKU, потенциал " + f"{total_effect:,.0f}" + " руб/мес"
    else:
        v5 = "Действий нет"

    data.append(["", v1, "", "", "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", "", "", ""])
    data.append(["", v4, "", "", "", "", "", "", "", ""])
    data.append(["", v5, "", "", "", "", "", "", "", ""])

    data.append(["", "", "", "", "", "", "", "", "", ""])
    data.append(["PremiumSubscription " + f"{PREMIUM_FIXED:,.0f}" + " руб/мес — постоянный расход, не в марже", "", "", "", "", "", "", "", "", ""])

    return data


def format_money(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    ops.append({"type": "merge", "range": "A1:J1"})
    ops.append({"type": "format", "range": "A1:J1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:J2"})
    ops.append({"type": "format", "range": "A2:J2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    # Размёрживаем строки 4-14 перед merge
    for r in range(4, 15):
        ops.append({"type": "unmerge", "range": f"A{r}:J{r}"})
    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_money = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    body_margin = CellFormat(
        textFormat=TextFormat(fontSize=12, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_center = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Легенда (строка 8)
    legend_fmt = CellFormat(
        textFormat=TextFormat(fontSize=9, italic=True, foregroundColor=MUTED_FG),
        backgroundColor=Color(0.98, 0.98, 0.98),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
    )
    ops.append({"type": "merge", "range": "A8:J8"})
    ops.append({"type": "format", "range": "A8:J8", "format": legend_fmt})
    ops.append({"type": "row_height", "row": 8, "height": 30})

    # ПО МЕСЯЦАМ — строка 9
    ops.append({"type": "merge", "range": "A9:J9"})
    ops.append({"type": "format", "range": "A9:J9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 28})

    # Заголовки таблицы — 10
    ops.append({"type": "format", "range": "A10:J10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 36})

    for r in range(11, 15):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — 16
    # Явно размёрживаем всё перед merge
    for r in range(16, 22):
        ops.append({"type": "unmerge", "range": f"A{r}:J{r}"})
    ops.append({"type": "merge", "range": "A16:J16"})
    ops.append({"type": "format", "range": "A16:J16", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 16, "height": 28})

    for r in range(17, 22):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Premium — 23
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A23:J23"})
    ops.append({"type": "format", "range": "A23:J23", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 23, "height": 26})

    ops.append({"type": "width", "col": "A", "width": 140})
    ops.append({"type": "width", "col": "B", "width": 130})
    ops.append({"type": "width", "col": "C", "width": 130})
    ops.append({"type": "width", "col": "D", "width": 120})
    ops.append({"type": "width", "col": "E", "width": 130})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 100})
    ops.append({"type": "width", "col": "H", "width": 100})
    ops.append({"type": "width", "col": "I", "width": 120})
    ops.append({"type": "width", "col": "J", "width": 130})

    ops.append({"type": "frozen", "rows": 4})

    n = batch_apply(ws, sid, ops)
    print("  Форматирование: " + str(n))

    # Цвет маржи G5:G15
    try:
        vals = ws.get("G5:G14")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0].strip().rstrip("%")
            try:
                m = float(v)
            except ValueError:
                continue
            r = 5 + i
            if r in (8, 9, 10, 11):
                continue
            if m < 5:
                bg, fg = BAD_BG, BAD_FG
            elif m < 15:
                bg, fg = WARN_BG, Color(0.5, 0.4, 0.0)
            else:
                bg, fg = GOOD_BG, GOOD_FG
            ops2.append({"type": "format", "range": f"G{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=fg),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print("  Цвет маржи: " + str(len(ops2)))
    except Exception as e:
        print("  WARN: " + str(e))

    # Цвет выводов 17-21
    try:
        vals = ws.get("B17:B21")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 17 + i
            if v.startswith("Критично") or v.startswith("Тонко") or v.startswith("Падение") or v.startswith("Себестоимость съедает"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("Норма") or v.startswith("Отлично") or v.startswith("Рост") or v.startswith("Услуги Ozon"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("Действия"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("Себестоимость"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0.0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"B{r}:J{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            batch_apply(ws, sid, ops3)
            print("  Цвет выводов: " + str(len(ops3)))
    except Exception as e:
        print("  WARN: " + str(e))


def sync_money(sh, con):
    print()
    print("[Лист ДЕНЬГИ]")
    ws = get_or_create_sheet(sh, "ДЕНЬГИ")
    data = build_money(con)
    clear_and_write(ws, data)
    print("  Записано строк: " + str(len(data)))
    format_money(ws)






def sync_result(sh, con):
    print("\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)




def build_result(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = "2026-08-01"

    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = profit = 0.0
    orders = 0
    for sku, cost_price, r, o in rows:
        r = r or 0
        o = o or 0
        cost_price = cost_price or 0
        c = cost_price * o
        cm = r * COMMISSION_PCT
        sv = r * SERVICES_PCT
        pb = r - c - cm - sv
        tx = pb * TAX_PCT if pb > 0 else 0
        rev += r
        cost += c
        profit += pb - tx
        orders += o
    margin = profit / rev if rev else 0
    avg = rev / orders if orders else 0

    con.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            run_at TEXT PRIMARY KEY,
            period_from TEXT, period_to TEXT,
            revenue REAL, profit REAL, margin REAL,
            orders INTEGER, avg_check REAL
        )
    """)
    con.commit()
    prev = con.execute("""
        SELECT run_at, revenue, profit, margin, orders, avg_check
        FROM dashboard_snapshots ORDER BY run_at DESC LIMIT 1
    """).fetchone()

    def delta(c, o):
        if not o:
            return "-"
        return f"{(c - o) / abs(o) * 100:+.1f}%"

    def verdict_delta(d_str):
        if d_str == "-" or d_str == "первый запуск":
            return "первый запуск"
        try:
            v = float(d_str.rstrip("%"))
        except ValueError:
            return "-"
        if v > 5:
            return "Рост"
        if v > 1:
            return "Небольшой рост"
        if v > -1:
            return "Без изменений"
        if v > -5:
            return "Снижение"
        return "Падение"

    data = [
        ["РЕЗУЛЬТАТ", "", "", "", ""],
        [f"период с 1 августа по {max_date}  (реальный старт бизнеса)", "", "", "", ""],
        ["", "", "", "", ""],
        ["Показатель", "Сейчас", "Прошлый запуск", "Дельта", "Оценка"],
    ]

    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev
        d_rev = delta(rev, p_rev)
        d_profit = delta(profit, p_profit)
        d_orders = delta(orders, p_orders)
        d_avg = delta(avg, p_avg)
        data.append(["Выручка", f"{rev:,.0f}", f"{p_rev:,.0f}", d_rev, verdict_delta(d_rev)])
        data.append(["Прибыль", f"{profit:,.0f}", f"{p_profit:,.0f}", d_profit, verdict_delta(d_profit)])
        data.append(["Маржа", f"{margin*100:.1f}%", f"{p_margin*100:.1f}%", "", ""])
        data.append(["Заказы", orders, p_orders, d_orders, verdict_delta(d_orders)])
        data.append(["Ср. чек", f"{avg:,.0f}", f"{p_avg:,.0f}", d_avg, verdict_delta(d_avg)])
    else:
        data.append(["Выручка", f"{rev:,.0f}", "-", "первый запуск", "-"])
        data.append(["Прибыль", f"{profit:,.0f}", "-", "первый запуск", "-"])
        data.append(["Маржа", f"{margin*100:.1f}%", "-", "-", "-"])
        data.append(["Заказов", orders, "-", "первый запуск", "-"])
        data.append(["Ср. чек", f"{avg:,.0f}", "-", "первый запуск", "-"])

    # ВЫВОДЫ
    data.append(["", "", "", "", ""])
    data.append(["ВЫВОДЫ", "", "", "", ""])

    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev

        if p_rev:
            rev_chg = (rev - p_rev) / abs(p_rev) * 100
            if rev_chg > 5:
                v1 = f"Выручка выросла на {rev_chg:+.1f}% - рост оборотов"
            elif rev_chg > 1:
                v1 = f"Выручка выросла на {rev_chg:+.1f}% - небольшой рост"
            elif rev_chg > -1:
                v1 = f"Выручка без изменений ({rev_chg:+.1f}%)"
            elif rev_chg > -5:
                v1 = f"Выручка снизилась на {rev_chg:+.1f}% - обратить внимание"
            else:
                v1 = f"Выручка упала на {rev_chg:+.1f}% - разобраться с причинами"
        else:
            v1 = "Нет данных для сравнения выручки"

        if p_profit and p_rev:
            profit_chg = (profit - p_profit) / abs(p_profit) * 100
            if profit_chg > rev_chg + 2:
                v2 = f"Прибыль растёт быстрее выручки ({profit_chg:+.1f}% vs {rev_chg:+.1f}%) - маржа улучшается"
            elif profit_chg < rev_chg - 2:
                v2 = f"Прибыль падает быстрее выручки ({profit_chg:+.1f}% vs {rev_chg:+.1f}%) - маржа ухудшается"
            else:
                v2 = f"Прибыль и выручка меняются одинаково ({profit_chg:+.1f}% vs {rev_chg:+.1f}%)"
        else:
            v2 = "Прибыль: нет данных для сравнения"

        m_prev_pct = p_margin * 100 if p_margin else 0
        m_curr_pct = margin * 100
        d_m = m_curr_pct - m_prev_pct
        if d_m > 1:
            v3 = f"Маржа выросла: {m_prev_pct:.1f}% -> {m_curr_pct:.1f}% ({d_m:+.1f} п.п.)"
        elif d_m < -1:
            v3 = f"Маржа упала: {m_prev_pct:.1f}% -> {m_curr_pct:.1f}% ({d_m:+.1f} п.п.)"
        else:
            v3 = f"Маржа стабильна: {m_curr_pct:.1f}%"

        if p_avg:
            avg_chg = (avg - p_avg) / abs(p_avg) * 100
            if avg_chg > 3:
                v4 = f"Средний чек вырос на {avg_chg:+.1f}% - клиенты берут дороже"
            elif avg_chg < -3:
                v4 = f"Средний чек упал на {avg_chg:+.1f}% - клиенты берут дешевле"
            else:
                v4 = f"Средний чек стабилен: {avg:,.0f} руб"
        else:
            v4 = f"Средний чек: {avg:,.0f} руб"

        if rev_chg > 1 and profit_chg > 1:
            v5 = "ИТОГ: бизнес растёт - продолжать в том же направлении"
        elif rev_chg < -1 and profit_chg < -1:
            v5 = "ИТОГ: бизнес сжимается - проверить убыточные SKU и цены"
        elif rev_chg > 0 and profit_chg < 0:
            v5 = "ИТОГ: обороты растут, но прибыль падает - растёт доля низкомаржинальных SKU"
        else:
            v5 = "ИТОГ: стабильность - использовать время для оптимизации"
    else:
        v1 = f"Первый запуск: выручка {rev:,.0f} руб, прибыль {profit:,.0f} руб"
        v2 = f"Маржа {margin*100:.1f}% - сравнение появится со следующего запуска"
        v3 = "Запусти sheets_sync.py повторно, чтобы увидеть динамику"
        v4 = ""
        v5 = ""

    data.append(["", v1, "", "", ""])
    data.append(["", v2, "", "", ""])
    data.append(["", v3, "", "", ""])
    if v4:
        data.append(["", v4, "", "", ""])
    if v5:
        data.append(["", v5, "", "", ""])

    data.append(["", "", "", "", ""])
    data.append([f"Предыдущий запуск: {prev[0] if prev else 'нет'}", "", "", "", ""])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT OR REPLACE INTO dashboard_snapshots
        (run_at, period_from, period_to, revenue, profit, margin, orders, avg_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, min_date, max_date, rev, profit, margin, orders, avg))
    con.commit()

    return data


def format_result(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    # Заголовок A1:E1
    ops.append({"type": "merge", "range": "A1:E1"})
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:E2"})
    ops.append({"type": "format", "range": "A2:E2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки таблицы — строка 4
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:E4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    # Данные 5-9
    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_val = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_delta = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_verdict = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    for r in range(5, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": body_val})
        ops.append({"type": "format", "range": f"D{r}", "format": body_delta})
        ops.append({"type": "format", "range": f"E{r}", "format": body_verdict})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — заголовок строка 11
    ops.append({"type": "merge", "range": "A11:E11"})
    ops.append({"type": "format", "range": "A11:E11", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 11, "height": 28})

    # Строки выводов 12-16
    for r in range(12, 17):
        ops.append({"type": "unmerge", "range": f"A{r}:E{r}"})
        ops.append({"type": "merge", "range": f"B{r}:E{r}"})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Предыдущий запуск — строка 18
    last_run = CellFormat(
        textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A18:E18"})
    ops.append({"type": "format", "range": "A18:E18", "format": last_run})
    ops.append({"type": "row_height", "row": 18, "height": 24})

    ops.append({"type": "width", "col": "A", "width": 160})
    ops.append({"type": "width", "col": "B", "width": 150})
    ops.append({"type": "width", "col": "C", "width": 150})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 240})

    ops.append({"type": "frozen", "rows": 4})

    ops.append({"type": "note", "cell": "D4",
                "note": "Дельта = изменение vs прошлый запуск. Зелёный: рост, красный: падение."})
    ops.append({"type": "note", "cell": "E4",
                "note": "Оценка: Рост >5%, Небольшой рост 1-5%, Без изменений +-1%, Снижение -1..-5%, Падение <-5%."})
    ops.append({"type": "note", "cell": "A11",
                "note": "Автоматические выводы. Обновляются при каждом запуске."})

    n = batch_apply(ws, sid, ops)
    print(f"  Основное форматирование: {n}")

    # Δ-цвета
    try:
        values = ws.get("D5:D9")
        ops2 = []
        for i, row in enumerate(values):
            if not row:
                continue
            v = row[0].strip()
            r = 5 + i
            if v.startswith("+") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=GOOD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=GOOD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
            elif v.startswith("-") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=BAD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Дельта-цвета: {len(ops2)}")
    except Exception as e:
        print(f"  WARN: {e}")

    # Цвет выводов 12-16
    try:
        vals = ws.get("B12:B16")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 12 + i
            if v.startswith("Выручка упала") or v.startswith("Маржа упала") or v.startswith("Прибыль падает") or v.startswith("бизнес сжимается") or v.startswith("ИТОГ: бизнес сжимается"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("ИТОГ") or v.startswith("Запусти"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("Выручка выросла") or v.startswith("Маржа выросла") or v.startswith("Средний чек вырос") or v.startswith("Прибыль растёт"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("Выручка снизилась") or v.startswith("Средний чек упал"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0.0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"B{r}:E{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            batch_apply(ws, sid, ops3)
            print(f"  Цвет выводов: {len(ops3)}")
    except Exception as e:
        print(f"  WARN: {e}")


def sync_result(sh, con):
    print()
    print("[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)



# ============ ЛИСТ ВВОД ============
def build_input(con):
    """Ручной ввод: остаток на счету, план закупок."""
    # Последний ввод остатка
    last_input = con.execute("""
        SELECT update_date, on_account, note FROM capital_input
        ORDER BY update_date DESC LIMIT 1
    """).fetchone()

    if last_input:
        update_date, on_account, note = last_input
    else:
        update_date, on_account, note = "", 0, ""

    # План закупок (активные, не оплаченные)
    procurements = con.execute("""
        SELECT id, due_date, supplier, amount, status
        FROM procurement_plan
        WHERE status = 'planned'
        ORDER BY due_date ASC
    """).fetchall()

    data = []
    data.append(["ВВОД ДАННЫХ", "", "", "", ""])
    data.append(["Заполняй раз в день/неделю. Значения идут в лист КАПИТАЛ.", "", "", "", ""])
    data.append(["", "", "", "", ""])
    data.append(["1. ОСТАТОК НА СЧЕТУ", "", "", "", ""])
    data.append(["Дата обновления (YYYY-MM-DD)", "Сумма на счету (руб)", "Комментарий", "", ""])
    data.append([update_date or "заполни", on_account or "", note or "", "", ""])
    data.append(["", "", "", "", ""])
    data.append(["2. ПЛАН ЗАКУПОК", "", "", "", ""])
    data.append(["Когда платить", "Кому", "Сколько руб", "Статус", "ID"])
    if procurements:
        for p in procurements:
            data.append([p["due_date"], p["supplier"] or "", p["amount"], p["status"], p["id"]])
    else:
        data.append(["пример: 2026-10-01", "Иванов (Сатин)", 50000, "planned", ""])
    data.append(["", "", "", "", ""])
    data.append(["3. ИНСТРУКЦИЯ", "", "", "", ""])
    data.append(["Остаток на счету", "ЛК Ozon → Финансы → Баланс, или ваш банк", "", "", ""])
    data.append(["План закупок", "Кому/сколько/когда платить поставщику", "", "", ""])
    data.append(["После ввода", "Запусти: py calc_capital_to_db.py", "", "", ""])
    return data


def format_input(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    ops.append({"type": "merge", "range": "A1:E1"})
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:E2"})
    ops.append({"type": "format", "range": "A2:E2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    for r in [4, 8, 13]:
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": section_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    input_cell = CellFormat(
        backgroundColor=Color(0xFF/255, 0xF9/255, 0xD6/255),
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    # 1. Остаток — заголовок и значение
    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})
    ops.append({"type": "format", "range": "A6", "format": input_cell})
    ops.append({"type": "format", "range": "B6", "format": input_cell})
    ops.append({"type": "format", "range": "C6:E6", "format": input_cell})
    ops.append({"type": "row_height", "row": 6, "height": 40})

    # 2. План закупок — заголовок и данные
    ops.append({"type": "format", "range": "A9:E9", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 9, "height": 32})
    for r in range(10, 15):
        ops.append({"type": "row_height", "row": r, "height": 28})

    # 3. Инструкция — строки 13-16
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(13, 17):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 28})

    for c, w in [("A", 240), ("B", 200), ("C", 160), ("D", 120), ("E", 80)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 2})

    ops.append({"type": "note", "cell": "B6",
                "note": "Открой ЛК Ozon - Финансы - Баланс. Скопируй сумму сюда. Раз в день."})
    ops.append({"type": "note", "cell": "A6",
                "note": "Введи сегодняшнюю дату в формате 2026-09-21"})
    ops.append({"type": "note", "cell": "A9",
                "note": "Строки для плана закупок. Одна строка = одна оплата поставщику."})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")


def sync_input(sh, con):
    print("")
    print("[Лист ВВОД]")
    ws = get_or_create_sheet(sh, "ВВОД")
    data = build_input(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_input(ws)


# ============ ЛИСТ КАПИТАЛ ============
def build_capital(con):
    """Блок КАПИТАЛ: где деньги, что забрать, прогноз, оборот."""

    # === Данные из БД ===
    last_input = con.execute("""
        SELECT update_date, on_account FROM capital_input
        ORDER BY update_date DESC LIMIT 1
    """).fetchone()
    if last_input:
        on_account = last_input[1] or 0
        input_date = last_input[0]
    else:
        on_account = 0
        input_date = "нет"

    # У Ozon к выплате — ТОЧНО из balance_history
    bh = con.execute("""
        SELECT closing_balance FROM balance_history
        ORDER BY fetched_at DESC LIMIT 1
    """).fetchone()
    if bh:
        owed_by_ozon = bh[0] or 0
    else:
        owed_by_ozon = 0

    frozen = con.execute("""
        SELECT SUM(cs.total_present * p.cost_price)
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        WHERE p.cost_price > 0 AND cs.total_present > 0
    """).fetchone()[0] or 0

    in_transit = 0

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    revenue_30 = con.execute(
        "SELECT SUM(revenue) FROM sales_daily WHERE date BETWEEN ? AND ?",
        (date_from, max_date)
    ).fetchone()[0] or 0

    cogs_30 = 0
    rows = con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
        GROUP BY p.sku
    """, (date_from, max_date)).fetchall()
    for r in rows:
        cogs_30 += (r[0] or 0) * (r[1] or 0)

    profit_30 = revenue_30 * 0.088
    tax_reserve = profit_30 * 0.15

    total_assets = on_account + owed_by_ozon + frozen + in_transit
    net_assets = total_assets - tax_reserve

    # === ЧТО ЗАБРАТЬ ===
    # Резерв закупок = план из procurement_plan (будущие платежи)
    today_str = datetime.now().strftime("%Y-%m-%d")
    reserve_proc = con.execute("""
        SELECT SUM(amount) FROM procurement_plan
        WHERE status = 'planned' AND due_date >= ?
    """, (today_str,)).fetchone()[0] or 0

    # Резерв штрафов = 3% от выручки
    reserve_fines = revenue_30 * 0.03

    free_money = on_account + owed_by_ozon - tax_reserve - reserve_proc - reserve_fines

    # === ПРОГНОЗ 14 ДНЕЙ ===
    # Заказы в доставке
    pending = con.execute("""
        SELECT COUNT(*), SUM(total_price) FROM pending_orders
        WHERE status IN ('delivering', 'sent_by_seller')
    """).fetchone()
    pending_count = pending[0] or 0
    pending_amount = pending[1] or 0

    today = datetime.now()

    # Реальные выплаты из payouts (ожидаемые)
    expected_payouts = con.execute("""
        SELECT period_begin, period_end, total_amount
        FROM payouts WHERE status = 'expected'
        ORDER BY period_begin DESC LIMIT 5
    """).fetchall()

    # План закупок
    payments = con.execute("""
        SELECT due_date, supplier, amount FROM procurement_plan
        WHERE status = 'planned' AND due_date BETWEEN ? AND ?
        ORDER BY due_date ASC
    """, (today.strftime("%Y-%m-%d"),
          (today + timedelta(days=14)).strftime("%Y-%m-%d"))).fetchall()

    # === ОБОРОТ ===
    turnover = revenue_30 / cogs_30 if cogs_30 > 0 else 0
    days_per_turn = 30 / turnover if turnover > 0 else 0

    # === ВЫВОДЫ ===
    verdicts = []

    if free_money > 50000:
        verdicts.append(("✅", f"Свободно {free_money:,.0f} ₽ — можно забрать без вреда для бизнеса"))
    elif free_money > 10000:
        verdicts.append(("⚠", f"Свободно только {free_money:,.0f} ₽ — забирать осторожно"))
    else:
        verdicts.append(("❌", f"Свободных денег нет ({free_money:,.0f} ₽) — всё в резервах"))

    frozen_pct = frozen / total_assets * 100 if total_assets else 0
    if frozen_pct > 70:
        verdicts.append(("❌", f"{frozen_pct:.0f}% капитала в товаре — ускорить оборот"))
    elif frozen_pct > 50:
        verdicts.append(("⚠", f"{frozen_pct:.0f}% капитала в товаре — на грани"))
    else:
        verdicts.append(("✅", f"{frozen_pct:.0f}% капитала в товаре — оборот здоровый"))

    if owed_by_ozon > 50000:
        verdicts.append(("💰", f"У Ozon заморожено {owed_by_ozon:,.0f} ₽ — ждём выплат"))

    if days_per_turn > 30:
        verdicts.append(("⚠", f"Оборот {days_per_turn:.0f} дней — медленно, цель 15-20 дней"))
    elif days_per_turn > 0:
        potential = cogs_30 * (30 / 20 - 30 / days_per_turn) if days_per_turn > 0 else 0
        verdicts.append(("✅", f"Оборот {days_per_turn:.0f} дней — норма. Ускорить до 15 = +{potential:,.0f} ₽ свободных"))

    if tax_reserve > 0:
        verdicts.append(("📊", f"Резерв налога УСН: {tax_reserve:,.0f} ₽ — отложить до квартала"))

    # === Собираем data ===
    data = []
    data.append(["КАПИТАЛ - где деньги, что забрать", "", "", "", ""])
    data.append([f"актуально на {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  данные из БД до {max_date}", "", "", "", ""])
    data.append(["", "", "", "", ""])

    # Блок 1. АКТИВЫ
    data.append(["1. ГДЕ ДЕНЬГИ (активы)", "", "", "", ""])
    data.append(["Место", "Сумма руб", "Доля %", "Комментарий", ""])
    data.append(["На счету", f"{on_account:,.0f}", f"{on_account/total_assets*100 if total_assets else 0:.1f}%",
                 f"обновлено {input_date}", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", f"{owed_by_ozon/total_assets*100 if total_assets else 0:.1f}%",
                 "точно из API", ""])
    data.append(["В товаре на складе", f"{frozen:,.0f}", f"{frozen/total_assets*100 if total_assets else 0:.1f}%",
                 "42 SKU с остатком", ""])

    data.append(["ИТОГО АКТИВОВ", f"{total_assets:,.0f}", "100%", "", ""])
    data.append(["Резерв налога УСН 15%", f"-{tax_reserve:,.0f}", "",
                 "отложить на налог", ""])
    data.append(["ЧИСТЫЕ АКТИВЫ", f"{net_assets:,.0f}", "",
                 "за вычетом налога", ""])
    data.append(["", "", "", "", ""])

    # Блок 2. ЧТО ЗАБРАТЬ
    data.append(["2. ЧТО ЗАБРАТЬ (свободные деньги)", "", "", "", ""])
    data.append(["", "Сумма руб", "", "Комментарий", ""])
    data.append(["На счету (в руках)", f"{on_account:,.0f}", "",
                 "уже доступно", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", "",
                 "придёт в течение недели", ""])
    data.append(["Резерв налога УСН", f"-{tax_reserve:,.0f}", "", "отложить на налог", ""])
    if reserve_proc > 0:
        data.append(["План закупок", f"-{reserve_proc:,.0f}", "",
                     "из листа ВВОД", ""])
    else:
        data.append(["План закупок", "0", "",
                     "нет плана", ""])
    data.append(["Резерв штрафов (3%)", f"-{reserve_fines:,.0f}", "",
                 "на риски и ошибки", ""])
    data.append(["МОЖНО ЗАБРАТЬ", f"{max(0, free_money):,.0f}", "",
                 "безопасно для бизнеса", ""])
    data.append(["", "", "", "", ""])

    # Блок 3. ПРОГНОЗ
    data.append(["3. КАССОВЫЙ ПРОГНОЗ (14 дней)", "", "", "", ""])
    data.append(["Что", "Когда", "Сумма руб", "", ""])

    # Приходы от Ozon — реальные недели
    if expected_payouts:
        for i, (pb, pe, amt) in enumerate(expected_payouts[:2], 1):
            data.append([f"Приход от Ozon (неделя {i})",
                         f"{pb[5:]} - {pe[5:]}",
                         f"+{amt:,.0f}",
                         "из API", ""])
    else:
        data.append(["Приход от Ozon", "нет данных", "0", "запусти fetch_payouts.py", ""])

    # Заказы к клиентам
    if pending_amount > 0:
        data.append([f"В заказах к клиентам ({pending_count} шт)",
                     "в доставке",
                     f"{pending_amount:,.0f}",
                     "уже продано, деньги после получения", ""])

    # План закупок
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])
    else:
        data.append(["Платежи поставщикам", "нет плана", "0", "", ""])

    data.append(["Налог УСН (аванс)", "раз в квартал", "-" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])
    data.append(["", "", "", "", ""])

    # Блок 4. ОБОРОТ
    data.append(["4. ОБОРОТ ДЕНЕГ (за 30 дней)", "", "", "", ""])
    data.append(["Метрика", "Значение", "", "Комментарий", ""])
    data.append(["Себестоимость проданного", f"{cogs_30:,.0f} руб", "", "за 30 дней", ""])
    data.append(["Получили выручки", f"{revenue_30:,.0f} руб", "", "", ""])
    data.append(["Оборот", f"{turnover:.2f}x", "",
                 "во сколько раз прокрутился рубль", ""])
    data.append(["Дней на оборот", f"{days_per_turn:.0f}", "",
                 "вложил → получил", ""])
    data.append(["", "", "", "", ""])

    # Блок 5. ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", ""])
    for icon, text in verdicts:
        data.append([icon + " " + text, "", "", "", ""])

    return data




def format_capital(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})
    # Явные unmerge для проблемных зон
    for r in [4, 5, 10, 11, 12, 14, 15, 20, 22, 23, 30, 31, 37]:
        ops.append({"type": "unmerge", "range": f"A{r}:E{r}"})
        ops.append({"type": "unmerge", "range": f"A{r}:Z{r}"})
        ops.append({"type": "unmerge", "range": f"A{r}:C{r}"})

    ops.append({"type": "merge", "range": "A1:E1"})
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:E2"})
    ops.append({"type": "format", "range": "A2:E2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    label_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    value_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    total_fmt = CellFormat(
        backgroundColor=Color(0.90, 0.94, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    total_val_fmt = CellFormat(
        backgroundColor=Color(0.90, 0.94, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    net_fmt = CellFormat(
        backgroundColor=Color(0.95, 0.98, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    net_val_fmt = CellFormat(
        backgroundColor=Color(0.95, 0.98, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    free_fmt = CellFormat(
        backgroundColor=GOOD_BG,
        textFormat=TextFormat(fontSize=13, bold=True, foregroundColor=GOOD_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    free_val_fmt = CellFormat(
        backgroundColor=GOOD_BG,
        textFormat=TextFormat(fontSize=13, bold=True, foregroundColor=GOOD_FG),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )

    # === Блок 1. ГДЕ ДЕНЬГИ (строки 4-13) ===
    ops.append({"type": "merge", "range": "A4:E4"})
    ops.append({"type": "format", "range": "A4:E4", "format": section_fmt})
    ops.append({"type": "row_height", "row": 4, "height": 30})

    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})

    # Строки 6-8 — активы (на счету, у Ozon, в товаре)
    for r in range(6, 9):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 9 — ИТОГО АКТИВОВ (синяя)
    ops.append({"type": "format", "range": "A9", "format": total_fmt})
    ops.append({"type": "format", "range": "B9:C9", "format": total_val_fmt})
    ops.append({"type": "row_height", "row": 9, "height": 30})

    # Строка 10 — Резерв налога
    minus_fmt = CellFormat(
        backgroundColor=Color(0xFF/255, 0xE5/255, 0xE5/255),
        textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    minus_val_fmt = CellFormat(
        backgroundColor=Color(0xFF/255, 0xE5/255, 0xE5/255),
        textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A10", "format": minus_fmt})
    ops.append({"type": "format", "range": "B10:C10", "format": minus_val_fmt})
    ops.append({"type": "row_height", "row": 10, "height": 30})

    # Строка 11 — ЧИСТЫЕ АКТИВЫ
    ops.append({"type": "format", "range": "A11", "format": net_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": net_val_fmt})
    ops.append({"type": "row_height", "row": 11, "height": 30})

    # === Блок 2. ЧТО ЗАБРАТЬ (строки 14-20) ===
    ops.append({"type": "merge", "range": "A13:E13"})
    ops.append({"type": "format", "range": "A13:E13", "format": section_fmt})
    ops.append({"type": "row_height", "row": 14, "height": 30})

    ops.append({"type": "format", "range": "A14:E14", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(15, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 21 — МОЖНО ЗАБРАТЬ (зелёная)
    ops.append({"type": "format", "range": "A20", "format": free_fmt})
    ops.append({"type": "format", "range": "B20:C20", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 20, "height": 34})

    # === Блок 3. ПРОГНОЗ (строки 22-28) ===
    ops.append({"type": "merge", "range": "A22:E22"})
    ops.append({"type": "format", "range": "A22:E22", "format": section_fmt})
    ops.append({"type": "row_height", "row": 22, "height": 30})

    ops.append({"type": "format", "range": "A23:E23", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 23, "height": 32})

    for r in range(24, 30):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=11), horizontalAlignment='CENTER', verticalAlignment='MIDDLE')})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # === Блок 4. ОБОРОТ (строки 30-34) ===
    ops.append({"type": "merge", "range": "A31:E31"})
    ops.append({"type": "format", "range": "A31:E31", "format": section_fmt})
    ops.append({"type": "row_height", "row": 30, "height": 30})

    ops.append({"type": "format", "range": "A32:E32", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 31, "height": 32})

    for r in range(33, 37):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # === Блок 5. ВЫВОДЫ (строки 37+) ===
    ops.append({"type": "merge", "range": "A38:E38"})
    ops.append({"type": "format", "range": "A38:E38", "format": section_fmt})
    ops.append({"type": "row_height", "row": 37, "height": 30})

    # Строки выводов 38-44 (7 максимум) — merge A:E
    for r in range(39, 46):
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "row_height", "row": r, "height": 32})

    for c, w in [("A", 300), ("B", 140), ("C", 100), ("D", 260), ("E", 80)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 2})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")

    # Цвет выводов
    try:
        vals = ws.get("A39:A45")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 39 + i
            if v.startswith("❌"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("⚠"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            elif v.startswith("✅"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            elif v.startswith("📊"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"A{r}:E{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {len(ops2)}")
    except Exception as e:
        print(f"  WARN: {e}")




def sync_capital(sh, con):
    print("")
    print("[Лист КАПИТАЛ]")
    ws = get_or_create_sheet(sh, "КАПИТАЛ")
    data = build_capital(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_capital(ws)


def main():
    print("=" * 80)
    print("ВЫГРУЗКА В GOOGLE SHEETS")
    print("=" * 80)

    client = get_client()
    sh = client.open_by_key(SHEET_ID)
    print(f"\nОткрыта таблица: {sh.title}")

    con = sqlite3.connect(DB)

    sync_manual(sh, con)
    sync_input(sh, con)
    sync_capital(sh, con)
    sync_today(sh, con)
    sync_actions(sh, con)
    sync_prices(sh, con)
    sync_frozen(sh, con)
    sync_money(sh, con)
    sync_result(sh, con)

    con.close()

    print("\n" + "=" * 80)
    print(f"  ГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
