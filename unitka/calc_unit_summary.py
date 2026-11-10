"""unitka/calc_unit_summary.py — лист «Юнит-сводка»: прибыль и минимальная цена по каждому SKU.

Переписан 2026-11-10. Раньше себестоимость и штуки брались из realization_daily
(по строке на каждое начисление → завышение в 2–3 раза), комиссия Ozon не учитывалась,
«мин. цена» была суммой расходов за год. Теперь расчёт — в unit_core, итог листа
сходится с P&L до рубля.

Запуск:  py -m unitka.calc_unit_summary            (пишет лист)
         py -m unitka.calc_unit_summary --local    (только печать, без Google Sheets)
"""
import os
import sys
from datetime import date, datetime

import gspread
from google.oauth2.service_account import Credentials

from .db import connect
from .finance_core import tax_settings, REGIME_DR
from . import settings, unit_core

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "Юнит-сводка"

HEADER = [
    "Артикул", "SKU", "Остаток, шт", "Продано, шт (за вычетом возвратов)", "Возвраты, шт",
    "Доход, ₽", "Комиссия Ozon, ₽", "Услуги Ozon по товару, ₽", "Себестоимость, ₽",
    "Прибыль до общих расходов, ₽", "Общие расходы Ozon (доля), ₽", "Прибыль, ₽", "Маржа, %",
    "Себестоимость 1 шт, ₽", "Комиссия, %", "Логистика и услуги на 1 шт, ₽",
    "МИН. ЦЕНА (в ноль), ₽", "Мин. цена с рекламой и общими расходами, ₽", "Цена для целевой маржи, ₽",
    "Текущая цена, ₽", "Запас до мин. цены, %", "Что делать",
]
STATUS_ORDER = ("🔴 ниже", "🔴 при", "🟡 не покрывает", "🟡 ниже", "🟢", "⚪")


def _status_rank(status: str) -> int:
    for i, prefix in enumerate(STATUS_ORDER):
        if status.startswith(prefix):
            return i
    return len(STATUS_ORDER)


def build(tax=None, unit=None, year=None):
    year = year or date.today().year
    conn = connect()
    cur = conn.cursor()
    eco = unit_core.sku_economics(cur, f"{year}-01-01", f"{year + 1}-01-01")
    prices = unit_core.min_prices(cur, eco, tax, unit)
    conn.close()

    items = []
    for sku, s in eco["skus"].items():
        m = prices[sku]
        has_activity = abs(s["income"]) > 0.005 or abs(s["svc_fixed"] + s["svc_pct"]) > 0.005
        if s["stock"] <= 0 and not has_activity:
            continue
        items.append({**s, **m})
    # сначала товар на складе (самые проблемные цены сверху), потом распроданный — по убыванию убытка
    items.sort(key=lambda i: (0, _status_rank(i["status"]), i["headroom_pct"] if i["headroom_pct"] is not None else 0)
               if i["stock"] > 0 else (1, 0, i["profit"]))

    t = eco["totals"]
    return {
        "year": year, "items": items, "totals": t, "params": t["price_params"],
        # совместимость со старым кодом
        "total_revenue": t["income"], "total_cogs": t["cogs"],
        "total_exp": t["ozon_total"], "total_profit": t["gross_profit"],
    }


def _r(v, nd=0):
    if v is None:
        return ""
    return int(round(v)) if nd == 0 else round(v, nd)


def table_rows(data):
    rows = []
    for i in data["items"]:
        rows.append([
            i["offer_id"] or "", i["sku"], i["stock"], _r(i["units"]), _r(i["returned"]),
            _r(i["income"], 2), _r(i["commission"], 2), _r(i["svc_fixed"] + i["svc_pct"], 2), _r(i["cogs"], 2),
            _r(i["direct_profit"], 2), _r(i["overhead"], 2), _r(i["profit"], 2),
            _r(i["margin_pct"], 1) if i["income"] > 0 else "",
            _r(i["cost_unit"], 2), _r(i["commission_pct"], 1), _r(i["fixed_unit"], 2),
            _r(i["min_direct"]) if i["min_direct"] else "—",
            _r(i["min_full"]) if i["min_full"] else "недостижимо",
            _r(i["target"]) if i["target"] else "недостижимо",
            _r(i["price"]) if i["price"] else "", _r(i["headroom_pct"], 1),
            i["status"] + (f" ({i['basis']})" if i["basis"] else ""),
        ])
    return rows


def summary_rows(data, tax):
    t, p = data["totals"], data["params"]
    regime = "доходы − расходы" if tax.get("regime") == REGIME_DR else "доходы"
    on_stock = [i for i in data["items"] if i["stock"] > 0]
    below = sum(1 for i in on_stock if i["status"].startswith("🔴"))
    thin = sum(1 for i in on_stock if i["status"].startswith("🟡 не покрывает"))
    left = 100 - p["store_commission_pct"] - p["other_pct"] - p["tax_pct"] - p["overhead_pct"]
    return [
        [f"ИТОГ ЗА {data['year']} ГОД (сходится с листом P&L)", "₽", "% от дохода"],
        ["Доход (цена + баллы Ozon + софинансирование)", round(t["income"], 2), 100],
        ["− Комиссия Ozon", -round(t["commission"], 2), -round(t["commission_pct"], 1)],
        ["− Услуги Ozon по товарам (логистика, эквайринг, возвраты)", -round(t["svc_sku"], 2),
         -round(t["svc_sku"] / t["income"] * 100, 1) if t["income"] else 0],
        ["− Общие расходы Ozon (реклама, подписки, штрафы, баллы за отзывы)", -round(t["overhead"], 2), -round(t["overhead_pct"], 1)],
        ["− Себестоимость проданного" + (" (текущий месяц — оценка)" if t["cogs_estimated"] else ""), -round(t["cogs"], 2),
         -round(t["cogs"] / t["income"] * 100, 1) if t["income"] else 0],
        ["ВАЛОВАЯ ПРИБЫЛЬ", round(t["gross_profit"], 2), round(t["margin_pct"], 1)],
        ["Продано, шт (за вычетом возвратов) / возвратов, шт", round(t["units"]), round(t["returned"])],
        ["", "", ""],
        ["КАК СЧИТАЕТСЯ МИН. ЦЕНА", "значение", "откуда"],
        ["Комиссия Ozon, % от цены продавца", round(p["store_commission_pct"], 1), "по товару — действующий тариф; здесь средняя за год"],
        ["Эквайринг и прочие процентные услуги, %", round(p["other_pct"], 1), "факт за год"],
        ["Налог, % от дохода", round(p["tax_pct"], 1), f"УСН «{regime}»: в точке безубыточности — минимальный налог" if tax.get("regime") == REGIME_DR else f"УСН «{regime}»"],
        ["Общие расходы Ozon, % от дохода", round(p["overhead_pct"], 1), "факт за год; своё значение — НАСТРОЙКИ «Общие расходы Ozon, %»"],
        ["Целевая маржа, %", round(p["target_margin_pct"], 1), "НАСТРОЙКИ «Целевая маржа, %»"],
        ["Логистика и услуги на 1 шт (средние), ₽", round(p["store_fixed_per_unit"]), "включая отмены и возвраты; по товару от 3 продаж — свои"],
        ["Остаётся продавцу с цены после Ozon, налога и общих расходов, %", round(left, 1), "из этого покрываются себестоимость и логистика"],
        ["Цены и тарифы Ozon обновлены", p["prices_fetched_at"] or "нет данных", "py fetch_current_prices.py (папка app)"],
        ["", "", ""],
        ["ВЫВОД", "", ""],
        [f"🔴 Товаров на складе с ценой ниже минимальной: {below} из {len(on_stock)} — каждая продажа в убыток, цену поднять до колонки «МИН. ЦЕНА»", "", ""],
        [f"🟡 Товаров, цена которых не покрывает рекламу и общие расходы: {thin} из {len(on_stock)}", "", ""],
    ]


def main():
    local = "--local" in sys.argv

    sh = None
    if not local:
        creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
    tax = tax_settings(sh)
    unit = settings.unit_params(sh)
    data = build(tax, unit)
    summary = summary_rows(data, tax)
    rows = table_rows(data)

    if local:
        for r in summary:
            print(" | ".join(str(x) for x in r))
        print(" | ".join(HEADER))
        for r in rows[:15]:
            print(" | ".join(str(x) for x in r))
        return

    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=300, cols=len(HEADER))
    need_rows = len(summary) + len(rows) + 10
    if ws.row_count < need_rows or ws.col_count < len(HEADER):
        ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, len(HEADER)))
    ws.clear()

    title = f"ЮНИТ-СВОДКА {data['year']}: прибыль и минимальная цена по товарам — обновлено {datetime.now():%d.%m.%Y %H:%M}"
    head_row = len(summary) + 4               # строка заголовка таблицы
    values = [[title], []] + summary + [[]] + [HEADER] + rows
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")

    sid = ws.id
    n_cols = len(HEADER)
    last = head_row + len(rows)
    blue = {"red": 0.18, "green": 0.33, "blue": 0.59}
    grey = {"red": 0.9, "green": 0.9, "blue": 0.9}
    white = {"red": 1, "green": 1, "blue": 1}

    def rng(r1, r2, c1, c2):
        return {"sheetId": sid, "startRowIndex": r1 - 1, "endRowIndex": r2, "startColumnIndex": c1 - 1, "endColumnIndex": c2}

    def fmt(r1, r2, c1, c2, cell, fields):
        return {"repeatCell": {"range": rng(r1, r2, c1, c2), "cell": {"userEnteredFormat": cell}, "fields": fields}}

    num = lambda p: {"numberFormat": {"type": "NUMBER", "pattern": p}}  # noqa: E731
    section_rows = [3 + i for i, r in enumerate(summary) if r[0] and (r[0].isupper() or r[0].startswith(("ИТОГ", "КАК", "ВЫВОД", "ВАЛОВАЯ")))]
    reqs = [
        {"unmergeCells": {"range": rng(1, max(last, 60), 1, n_cols)}},
        fmt(1, max(last, ws.row_count), 1, n_cols, {}, "userEnteredFormat"),
        {"mergeCells": {"range": rng(1, 1, 1, 8), "mergeType": "MERGE_ALL"}},
        fmt(1, 1, 1, n_cols, {"backgroundColor": blue, "textFormat": {"bold": True, "fontSize": 13, "foregroundColor": white}},
            "userEnteredFormat(backgroundColor,textFormat)"),
        fmt(3, 2 + len(summary), 2, 2, num("#,##0"), "userEnteredFormat.numberFormat"),
        fmt(head_row, head_row, 1, n_cols,
            {"backgroundColor": grey, "textFormat": {"bold": True}, "wrapStrategy": "WRAP",
             "verticalAlignment": "MIDDLE", "horizontalAlignment": "CENTER"},
            "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment,horizontalAlignment)"),
        fmt(head_row, head_row, 17, 17, {"backgroundColor": {"red": 1, "green": 0.85, "blue": 0.4}}, "userEnteredFormat.backgroundColor"),
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": head_row, "frozenColumnCount": 1}},
                                   "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": head_row - 1, "endIndex": head_row},
                                       "properties": {"pixelSize": 62}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                       "properties": {"pixelSize": 330}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": n_cols - 1},
                                       "properties": {"pixelSize": 105}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": n_cols - 1, "endIndex": n_cols},
                                       "properties": {"pixelSize": 380}, "fields": "pixelSize"}},
    ]
    for r in section_rows:
        reqs.append(fmt(r, r, 1, 3, {"textFormat": {"bold": True}, "backgroundColor": grey}, "userEnteredFormat(textFormat,backgroundColor)"))
    if rows:
        reqs += [
            fmt(head_row + 1, last, 6, 12, num("#,##0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 14, 14, num("#,##0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 16, 20, num("#,##0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 13, 13, num("0.0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 15, 15, num("0.0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 21, 21, num("0.0"), "userEnteredFormat.numberFormat"),
            fmt(head_row + 1, last, 17, 17, {"textFormat": {"bold": True}, "backgroundColor": {"red": 1, "green": 0.95, "blue": 0.8}},
                "userEnteredFormat(textFormat,backgroundColor)"),
        ]
    sh.batch_update({"requests": reqs})

    t = data["totals"]
    print(f"Лист «{SHEET_TITLE}» обновлён. Доход {t['income']:,.0f} | валовая прибыль {t['gross_profit']:,.0f} "
          f"(P&L: {t['pnl_gross_profit']:,.0f}) | SKU в таблице: {len(rows)}")


if __name__ == "__main__":
    main()
