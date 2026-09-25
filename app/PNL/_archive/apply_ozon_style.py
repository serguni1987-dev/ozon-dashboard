# apply_ozon_style.py — стиль листа P&L по образцу 2024.
# Значения НЕ трогает, только формат. Батч режется на чанки.
import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CRED = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(sync_pnl.SHEET_ID)
ws = sh.worksheet("P&L")
sid = ws.id

def rgb(h):
    h = h.lstrip("#")
    return {"red":   int(h[0:2],16)/255,
            "green": int(h[2:4],16)/255,
            "blue":  int(h[4:6],16)/255}

WHITE     = rgb("FFFFFF")
DARK      = rgb("000000")
HEAD_BG   = rgb("2F5496")   # тёмно-синий заголовок
HEAD_FG   = rgb("FFFFFF")
YEAR_BG   = rgb("D9E2F3")   # светло-синий «Всего за год»
QUART_BG  = rgb("E4DFEC")   # светло-фиолетовый кварталы
GREEN_BG  = rgb("C6E0B4")   # прибыль
GREEN_FG  = rgb("375623")
ORANGE_BG = rgb("FCE4D6")   # расходы
ORANGE_FG = rgb("833C0C")
RED_BG    = rgb("F4CCCC")
RED_FG    = rgb("990000")
GREY      = rgb("808080")
BORDER    = rgb("BFBFBF")

def grid(r0, r1, c0, c1):
    return {"sheetId": sid,
            "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}

def fmt_cell(bg=None, fg=None, bold=False, italic=False, size=11, align=None):
    cf = {}
    if bg: cf["backgroundColor"] = bg
    tf = {"fontSize": size}
    if fg: tf["foregroundColor"] = fg
    if bold: tf["bold"] = True
    if italic: tf["italic"] = True
    cf["textFormat"] = tf
    if align: cf["horizontalAlignment"] = align
    return cf

reqs = []

# 1. Заголовок — объединить A1:S1, тёмный текст, 18pt
reqs.append({"unmergeCells": {"range": grid(0,1,0,19)}})
reqs.append({"mergeCells": {"range": grid(0,1,0,19), "mergeType": "MERGE_ALL"}})
reqs.append({"repeatCell": {
    "range": grid(0,1,0,19),
    "cell": {"userEnteredFormat": fmt_cell(bg=WHITE, fg=DARK, bold=True, size=18, align="CENTER")},
    "fields": "userEnteredFormat"}})
reqs.append({"updateDimensionProperties": {
    "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
    "properties": {"pixelSize": 48}, "fields": "pixelSize"}})

# 2. Шапка — тёмно-синий фон, белый, центр
reqs.append({"repeatCell": {
    "range": grid(1,2,0,19),
    "cell": {"userEnteredFormat": fmt_cell(bg=HEAD_BG, fg=HEAD_FG, bold=True, size=11, align="CENTER")},
    "fields": "userEnteredFormat"}})
reqs.append({"updateDimensionProperties": {
    "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
    "properties": {"pixelSize": 40}, "fields": "pixelSize"}})

# 3. Колонка B — светло-синий
reqs.append({"repeatCell": {
    "range": grid(2, 47, 1, 2),
    "cell": {"userEnteredFormat": {"backgroundColor": YEAR_BG}},
    "fields": "userEnteredFormat.backgroundColor"}})

# 4. Кварталы O:R — светло-фиолетовый
reqs.append({"repeatCell": {
    "range": grid(2, 47, 14, 18),
    "cell": {"userEnteredFormat": {"backgroundColor": QUART_BG}},
    "fields": "userEnteredFormat.backgroundColor"}})

# 5. Знак чистой прибыли
net_val = 0.0
try:
    v = ws.acell("B43").value
    if v:
        net_val = float(str(v).replace(" ", "").replace("\xa0","")
                        .replace(",",".").replace("₽","").replace("%","").strip())
except Exception:
    pass
NET_BG, NET_FG = (GREEN_BG, GREEN_FG) if net_val >= 0 else (RED_BG, RED_FG)

# 6. Секции
SECTIONS = {
    8:  (GREEN_BG,  GREEN_FG),    # ДОХОДЫ
    14: (ORANGE_BG, ORANGE_FG),   # ПРЯМЫЕ РАСХОДЫ
    29: (ORANGE_BG, ORANGE_FG),   # Себестоимость
    31: (GREEN_BG,  GREEN_FG),    # ВАЛОВАЯ
    33: (QUART_BG,  DARK),        # Операционные
    39: (GREEN_BG,  GREEN_FG),    # EBITDA
    41: (ORANGE_BG, ORANGE_FG),   # Налоги
    43: (NET_BG,    NET_FG),      # ЧИСТАЯ
    46: (GREEN_BG,  GREEN_FG),    # Нераспределённая
    47: (GREEN_BG,  GREEN_FG),    # Накопленная
}
for r, (bg, fg) in SECTIONS.items():
    reqs.append({"repeatCell": {
        "range": grid(r-1, r, 0, 19),
        "cell": {"userEnteredFormat": fmt_cell(bg=bg, fg=fg, bold=True, size=11)},
        "fields": "userEnteredFormat"}})

# 7. Подстроки — серые italic
for r in (3,4,5,6, 17,18,19,20, 22,23, 34,35,36,37, 44,45):
    reqs.append({"repeatCell": {
        "range": grid(r-1, r, 0, 1),
        "cell": {"userEnteredFormat": fmt_cell(fg=GREY, italic=True, size=10)},
        "fields": "userEnteredFormat"}})

# 8. Выравнивание
reqs.append({"repeatCell": {
    "range": grid(2, 47, 1, 19),
    "cell": {"userEnteredFormat": {"horizontalAlignment": "RIGHT"}},
    "fields": "userEnteredFormat.horizontalAlignment"}})
reqs.append({"repeatCell": {
    "range": grid(2, 47, 0, 1),
    "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
    "fields": "userEnteredFormat.horizontalAlignment"}})

# 9. Формат чисел: пробел как разделитель, без ₽
NUM = '# ##0.00;-# ##0.00'
reqs.append({"repeatCell": {
    "range": grid(2, 47, 1, 19),
    "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": NUM}}},
    "fields": "userEnteredFormat.numberFormat"}})
# ROI — 0%
reqs.append({"repeatCell": {
    "range": grid(43, 44, 1, 19),
    "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": '0%'}}},
    "fields": "userEnteredFormat.numberFormat"}})

# 10. Ширины
reqs.append({"updateDimensionProperties": {
    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
    "properties": {"pixelSize": 320}, "fields": "pixelSize"}})
reqs.append({"updateDimensionProperties": {
    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
    "properties": {"pixelSize": 120}, "fields": "pixelSize"}})
for i in range(2, 19):
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i+1},
        "properties": {"pixelSize": 85}, "fields": "pixelSize"}})

# 11. Заморозка
reqs.append({"updateSheetProperties": {
    "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
    "fields": "gridProperties.frozenRowCount"}})

# 12. Границы
reqs.append({"updateBorders": {
    "range": grid(0,1,0,19),
    "bottom": {"style": "SOLID_THICK", "color": HEAD_BG}}})
for r in [8, 14, 31, 33, 39, 41, 43, 46, 47]:
    reqs.append({"updateBorders": {
        "range": grid(r-1, r, 0, 19),
        "top":    {"style": "SOLID", "color": BORDER},
        "bottom": {"style": "SOLID", "color": BORDER}}})

# ── Применяем чанками по 50 (защита от «всё-или-ничего») ──
total = 0
for i in range(0, len(reqs), 50):
    chunk = reqs[i:i+50]
    try:
        sh.batch_update({"requests": chunk})
        total += len(chunk)
    except Exception as e:
        print(f"[FAIL] чанк {i//50} ({len(chunk)} запросов): {e}")
        # продолжаем с остальными
print(f"[OK] Применено {total} из {len(reqs)} запросов")
print(f"https://docs.google.com/spreadsheets/d/{sync_pnl.SHEET_ID}/edit")
