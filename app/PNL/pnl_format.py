# pnl_format.py — оформление листа P&L (50 строк).
# Накладывает стиль поверх данных после sync_pnl.py. Значения не трогает.
import os, gspread
from google.oauth2.service_account import Credentials
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import sync_pnl

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]


def rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255}


WHITE     = rgb("FFFFFF")
BLACK     = rgb("000000")
GREY_TXT  = rgb("666666")
NAVY      = rgb("2F5496")
HEAD_FG   = rgb("FFFFFF")
YEAR_BG   = rgb("D9E2F3")
QUART_BG  = rgb("E4DFEC")
GREEN_BG  = rgb("C6E0B4")
GREEN_FG  = rgb("1F4E1F")
RED_TXT   = rgb("833C0C")
ORANGE_BG = rgb("FCE4D6")
RED_BG    = rgb("F4CCCC")
RED_FG    = rgb("7F0000")
ORANGE_FG = rgb("7F3F00")
BORDER    = rgb("BFBFBF")
ZERO_BG   = rgb("E7E6E6")


def grid(sid, r0, r1, c0=0, c1=20):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}


def cell(bg=None, fg=None, bold=False, italic=False, size=11, align=None):
    cf = {"textFormat": {"bold": bold, "italic": italic, "fontSize": size}}
    if fg: cf["textFormat"]["foregroundColor"] = fg
    if bg: cf["backgroundColor"] = bg
    if align: cf["horizontalAlignment"] = align
    return cf


def build_requests(sid, net_val, n_cf_existing=0):
    reqs = []; N = 50

    # Старые правила условного форматирования удаляем: каждый запуск добавлял
    # свои 7 правил заново, за месяцы накопилось >200 дублей (тормозит лист).
    for _ in range(n_cf_existing):
        reqs.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}})

    # Заголовок (строка 1)
    # Заголовок не объединяем: объединённая A1:T1 не даёт заморозить колонку A,
    # а без заморозки названия строк пропадают при прокрутке к кварталам.
    reqs.append({"unmergeCells": {"range": grid(sid, 0, 1)}})
    reqs.append({"repeatCell": {"range": grid(sid, 0, 1),
        "cell": {"userEnteredFormat": cell(bg=NAVY, fg=HEAD_FG, bold=True, size=16, align="LEFT")},
        "fields": "userEnteredFormat"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 45}, "fields": "pixelSize"}})

    # Шапка (строка 2)
    reqs.append({"repeatCell": {"range": grid(sid, 1, 2),
        "cell": {"userEnteredFormat": cell(bg=NAVY, fg=HEAD_FG, bold=True, size=11, align="CENTER")},
        "fields": "userEnteredFormat"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 36}, "fields": "pixelSize"}})

    # Фон B (год) и кварталов
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 1, 2),
        "cell": {"userEnteredFormat": {"backgroundColor": YEAR_BG}},
        "fields": "userEnteredFormat.backgroundColor"}})
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 14, 18),
        "cell": {"userEnteredFormat": {"backgroundColor": QUART_BG}},
        "fields": "userEnteredFormat.backgroundColor"}})

    # Секции (1-idx)
    for r, (bg, fg) in {
        8:  (GREEN_BG, GREEN_FG),    # ДОХОДЫ
        14: (ORANGE_BG, RED_TXT),    # Прямые
        34: (GREEN_BG, GREEN_FG),    # ВАЛОВАЯ
        42: (GREEN_BG, GREEN_FG),    # EBITDA
        44: (None, RED_TXT),         # Налоги
        49: (GREEN_BG, GREEN_FG),    # Нераспределённая
        50: (GREEN_BG, GREEN_FG),    # Накопленная
    }.items():
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=bg, fg=fg, bold=True, size=11)},
            "fields": "userEnteredFormat"}})

    # ЧИСТАЯ (46) — зелёная/красная
    bg, fg = (GREEN_BG, GREEN_FG) if net_val >= 0 else (RED_BG, RED_FG)
    reqs.append({"repeatCell": {"range": grid(sid, 45, 46),
        "cell": {"userEnteredFormat": cell(bg=bg, fg=fg, bold=True, size=13)},
        "fields": "userEnteredFormat"}})

    # Себестоимость (32) — красный текст
    reqs.append({"repeatCell": {"range": grid(sid, 31, 32),
        "cell": {"userEnteredFormat": cell(fg=RED_TXT, bold=True, size=11)},
        "fields": "userEnteredFormat"}})

    # C — узкая, серая italic
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 2, 3),
        "cell": {"userEnteredFormat": cell(bg=WHITE, fg=GREY_TXT, italic=True, size=10)},
        "fields": "userEnteredFormat"}})
    # T — серая italic, LEFT
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 19, 20),
        "cell": {"userEnteredFormat": cell(bg=WHITE, fg=GREY_TXT, italic=True, size=10, align="LEFT")},
        "fields": "userEnteredFormat"}})

    # Родители bold (16 фулфилмент, 21 маркетинг, 36 операционные)
    for r in (16, 21, 36):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=WHITE, fg=BLACK, bold=True, size=11)},
            "fields": "userEnteredFormat"}})

    # Дети — серые italic
    for r in (17, 18, 19, 20, 22, 23, 24, 25, 26, 37, 38, 39, 40):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=WHITE, fg=GREY_TXT, italic=True, size=10)},
            "fields": "userEnteredFormat"}})

    # Справочно (3-6)
    for r in (3, 4, 5, 6):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=WHITE, fg=BLACK, size=11)},
            "fields": "userEnteredFormat"}})

    # ROI (47) и Дивиденды (48)
    for r in (47, 48):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=WHITE, fg=GREY_TXT, italic=True, size=10)},
            "fields": "userEnteredFormat"}})

    # Обычные
    for r in (9, 10, 11, 12, 15, 27, 28, 29, 30):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": cell(bg=WHITE, fg=BLACK, size=11)},
            "fields": "userEnteredFormat"}})

    # Пустые
    for r in (7, 13, 31, 33, 35, 41, 43, 45):
        reqs.append({"repeatCell": {"range": grid(sid, r - 1, r),
            "cell": {"userEnteredFormat": {"backgroundColor": WHITE}},
            "fields": "userEnteredFormat.backgroundColor"}})

    # Выравнивание
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 0, 1),
        "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT"}},
        "fields": "userEnteredFormat.horizontalAlignment"}})
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 1, 20),
        "cell": {"userEnteredFormat": {"horizontalAlignment": "RIGHT"}},
        "fields": "userEnteredFormat.horizontalAlignment"}})

    # Числовой формат: RUB для B:T
    RUB = '# ##0;[Red]-# ##0'   # без копеек: P&L читают в тысячах, копейки — шум
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 1, 20),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": RUB}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # Заказы (строка 3) — целые без копеек
    reqs.append({"repeatCell": {"range": grid(sid, 2, 3, 1, 20),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": '0'}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # C — проценты (кроме строки 3)
    reqs.append({"repeatCell": {"range": grid(sid, 2, N, 2, 3),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": '0.00" %"'}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # ROI (47) — проценты
    reqs.append({"repeatCell": {"range": grid(sid, 46, 47, 1, 20),
        "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": '0.00" %"'}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # Ширины колонок
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 320}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 120}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
        "properties": {"pixelSize": 75}, "fields": "pixelSize"}})
    for i in range(3, 19):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": 85}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 19, "endIndex": 20},
        "properties": {"pixelSize": 115}, "fields": "pixelSize"}})

    # CF на T (вердикты)
    for prefix, bg, fg in [("!!", RED_BG, RED_FG),
                           ("⚠", ORANGE_BG, ORANGE_FG),
                           ("✓", GREEN_BG, GREEN_FG)]:
        reqs.append({"addConditionalFormatRule": {
            "rule": {
                "ranges": [grid(sid, 2, N, 19, 20)],
                "booleanRule": {
                    "condition": {"type": "TEXT_STARTS_WITH",
                                  "values": [{"userEnteredValue": prefix}]},
                    "format": {"backgroundColor": bg,
                               "textFormat": {"foregroundColor": fg, "bold": True}}
                }
            }, "index": 0}})

    # CF на B (год): >0 зелёный, <0 красный, =0 серый
    rngB = [grid(sid, 2, N, 1, 2)]   # B3:B50
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": rngB,
        "booleanRule": {
            "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "0"}]},
            "format": {"backgroundColor": GREEN_BG,
                       "textFormat": {"foregroundColor": GREEN_FG, "bold": True}}
        }}, "index": 1}})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": rngB,
        "booleanRule": {
            "condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]},
            "format": {"backgroundColor": RED_BG,
                       "textFormat": {"foregroundColor": RED_FG, "bold": True}}
        }}, "index": 2}})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": rngB,
        "booleanRule": {
            "condition": {"type": "NUMBER_EQ", "values": [{"userEnteredValue": "0"}]},
            "format": {"backgroundColor": ZERO_BG,
                       "textFormat": {"foregroundColor": GREY_TXT}}
        }}, "index": 3}})

    # CF на месяцы и кварталы итоговых строк (валовая, EBITDA, чистая, нераспределённая, накопленная)
    rngRes = [grid(sid, r - 1, r, 3, 19) for r in (34, 42, 46, 49, 50)]
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": rngRes,
        "booleanRule": {
            "condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]},
            "format": {"backgroundColor": RED_BG, "textFormat": {"foregroundColor": RED_FG, "bold": True}}
        }}, "index": 4}})
    reqs.append({"addConditionalFormatRule": {"rule": {
        "ranges": rngRes,
        "booleanRule": {
            "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "0"}]},
            "format": {"backgroundColor": GREEN_BG, "textFormat": {"foregroundColor": GREEN_FG, "bold": True}}
        }}, "index": 5}})

    # Примечания к ключевым строкам — откуда цифра и с чем сверять
    NOTES = {
        8:  "Доходы = Отчёт о реализации: цена продажи + баллы Ozon + программы партнёров.\n"
            "Сверять с ЛК «Экономика магазина → Начислено» и Точкой «Выручка».",
        14: "Все удержания Ozon: комиссия + услуги (со знаком, компенсации плюсом).\n"
            "Сверять с ЛК «Экономика магазина → Расходы» и Точкой «Расходы + Реклама».",
        32: "Себестоимость = (доставлено − возвращено) × закупочная цена (product_cost_history).\n"
            "Текущий месяц без отчёта о реализации — оценка по начислениям.",
        34: "Валовая прибыль = Доходы − удержания Ozon − себестоимость. Это деньги до налогов и взносов.",
        40: "Фиксированные страховые взносы ИП за год / 12. Входят в расходы при УСН «доходы − расходы».",
        44: "УСН «доходы − расходы», ставка из НАСТРОЙКИ!B1; не меньше 1% от доходов (минимальный налог).\n"
            "Помесячно — оценка. Налог считается за год — см. лист «Налоги».",
        46: "Чистая прибыль = EBITDA + налог (налог со знаком минус). Ручные операционные расходы (строки 37–39) учитываются.",
        50: "Накопленная прибыль — нарастающим итогом с января.",
    }
    for r, note in NOTES.items():
        reqs.append({"updateCells": {
            "range": grid(sid, r - 1, r, 0, 1),
            "rows": [{"values": [{"note": note}]}],
            "fields": "note"}})

    # Границы
    reqs.append({"updateBorders": {"range": grid(sid, 0, 1),
        "bottom": {"style": "SOLID_THICK", "color": NAVY}}})
    for r in (8, 14, 16, 21, 32, 34, 36, 42, 44, 46, 49, 50):
        reqs.append({"updateBorders": {"range": grid(sid, r - 1, r),
            "top": {"style": "SOLID", "color": BORDER},
            "bottom": {"style": "SOLID", "color": BORDER}}})

    # Freeze: строки 1–2 и колонка A (заголовок больше не объединён)
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
            "gridProperties": {"frozenRowCount": 2, "frozenColumnCount": 1}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})

    return reqs


def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID)
    ws = sh.worksheet("P&L"); sid = ws.id

    net_val = 0.0
    try:
        v = ws.acell("B46").value
        if v:
            net_val = float(str(v).replace(" ", "").replace("\xa0", "")
                            .replace(",", ".").replace("₽", "").replace("%", "").strip())
    except Exception:
        pass
    print(f"Чистая прибыль (B46) = {net_val}")

    n_cf = 0
    try:
        meta = sh.fetch_sheet_metadata({"fields": "sheets(properties.sheetId,conditionalFormats)"})
        for sht in meta.get("sheets", []):
            if sht.get("properties", {}).get("sheetId") == sid:
                n_cf = len(sht.get("conditionalFormats", []))
    except Exception as e:
        print(f"[!] Не прочитал список CF-правил ({e}) — старые правила останутся")
    print(f"Старых CF-правил: {n_cf}")

    reqs = build_requests(sid, net_val, n_cf)
    total = 0
    for i in range(0, len(reqs), 50):
        chunk = reqs[i:i + 50]
        try:
            sh.batch_update({"requests": chunk})
            total += len(chunk)
        except Exception as e:
            print(f"[FAIL] чанк {i // 50}: {e}")
    print(f"[OK] Стилей применено: {total}/{len(reqs)}")


if __name__ == "__main__":
    main()