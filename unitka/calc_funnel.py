"""unitka/calc_funnel.py — лист «Воронка» (показы→просмотры→корзина→заказ→выкуп)."""
import argparse
import logging
from datetime import date, timedelta, datetime
import os

import gspread
from google.oauth2.service_account import Credentials

from .db import connect

log = logging.getLogger("calc_funnel")

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "Воронка"

HEADER = [
    "SKU", "Артикул", "Показы", "Просмотры", "В корзину", "Заказы", "Выкупы",
    "Показ→Просмотр %", "Просмотр→Корзина %", "Корзина→Заказ %", "Заказ→Выкуп %",
    "Показ→Заказ %", "Позиция", "ДРР %", "Остаток", "Статус",
]

def _pct(a, b):
    if not b: return 0.0
    return round(a / b * 100, 2)

def _load_stocks(conn):
    """Возвращает {sku: остаток} на последнюю дату."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if not last_date:
        return {}
    cur.execute("""
        SELECT sku, (fbo_present + fbs_present) AS qty
        FROM stock_daily WHERE date = ?
    """, (last_date,))
    return {str(r[0]): (r[1] or 0) for r in cur.fetchall()}

def _load_period(dfrom: str, dto: str, only_in_stock: bool = False):
    conn = connect()
    cur = conn.cursor()
    stocks = _load_stocks(conn)

    cur.execute("""
        SELECT am.sku, am.offer_id, am.impressions, am.views, am.cart,
               am.orders, am.buyouts, am.position, am.drr
        FROM analytics_manual am
        WHERE am.date BETWEEN ? AND ?
    """, (dfrom, dto))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return []

    agg = {}
    for r in rows:
        sku = str(r[0])
        if sku not in agg:
            agg[sku] = {"offer_id": r[1], "impressions": 0, "views": 0, "cart": 0,
                        "orders": 0, "buyouts": 0, "position_sum": 0, "position_n": 0,
                        "drr_sum": 0, "drr_n": 0}
        a = agg[sku]
        a["impressions"] += r[2] or 0
        a["views"] += r[3] or 0
        a["cart"] += r[4] or 0
        a["orders"] += r[5] or 0
        a["buyouts"] += r[6] or 0
        if r[7]: a["position_sum"] += r[7]; a["position_n"] += 1
        if r[8]: a["drr_sum"] += r[8]; a["drr_n"] += 1

    # Фильтры
    result = []
    for sku, a in agg.items():
        if a["impressions"] < 10:
            continue
        qty = stocks.get(sku, 0)
        if only_in_stock and qty <= 0:
            continue

        pos = round(a["position_sum"] / a["position_n"], 1) if a["position_n"] else None
        drr = round(a["drr_sum"] / a["drr_n"], 1) if a["drr_n"] else None

        # Статус
        if a["orders"] == 0 and a["impressions"] >= 100:
            status = "🔴 Показы без заказов"
        elif a["orders"] == 0 and qty > 0:
            status = "🟡 В наличии, но не покупают"
        elif a["orders"] > 0 and qty == 0:
            status = "🟢 Продаётся, но нет остатка (закупить)"
        elif _pct(a["orders"], a["impressions"]) >= 1.5:
            status = "🟢 Отличная конверсия"
        else:
            status = ""

        result.append({
            "sku": sku, "offer_id": a["offer_id"],
            "impressions": a["impressions"], "views": a["views"],
            "cart": a["cart"], "orders": a["orders"], "buyouts": a["buyouts"],
            "c1": _pct(a["views"], a["impressions"]),
            "c2": _pct(a["cart"], a["views"]),
            "c3": _pct(a["orders"], a["cart"]),
            "c4": _pct(a["buyouts"], a["orders"]),
            "c_total": _pct(a["orders"], a["impressions"]),
            "position": pos, "drr": drr, "qty": qty, "status": status,
        })
    return result

def _build_report(items):
    if not items:
        return (["⚪ Нет данных. Загрузите xlsx через load_sales_xlsx."], [["", ""]], [], [])

    meaningful = [i for i in items if i["impressions"] >= 100] or items

    total_imp = sum(i["impressions"] for i in meaningful)
    total_ord = sum(i["orders"] for i in meaningful)
    total_cart = sum(i["cart"] for i in meaningful)
    total_views = sum(i["views"] for i in meaningful)

    overall_c = _pct(total_ord, total_imp)
    c_view = _pct(total_views, total_imp)
    c_cart = _pct(total_cart, total_views)
    c_order = _pct(total_ord, total_cart)

    main = [f"🟢 Конверсия показ→заказ (SKU с >100 показов): {overall_c}%"]
    narrow_name, narrow_val = min(
        [("показ→просмотр", c_view), ("просмотр→корзина", c_cart), ("корзина→заказ", c_order)],
        key=lambda x: x[1]
    )
    main.append(f"🟡 Узкое горлышко: {narrow_name} ({narrow_val}%)")
    top = sorted(meaningful, key=lambda x: x["c_total"], reverse=True)[:3]
    for t in top:
        main.append(f"🟢 Топ: SKU {t['sku']} — конв. {t['c_total']}%")

    summary = [["Метрика", "Значение"],
               ["Показы (всего)", f"{total_imp:,}"],
               ["Просмотры", f"{total_views:,}"],
               ["В корзину", f"{total_cart:,}"],
               ["Заказы", f"{total_ord:,}"],
               ["Показ→Просмотр", f"{c_view}%"],
               ["Просмотр→Корзина", f"{c_cart}%"],
               ["Корзина→Заказ", f"{c_order}%"],
               ["Показ→Заказ", f"{overall_c}%"]]

    problems = []
    # 1. Показы есть, но нет заказов
    blind = [i for i in items if i["impressions"] >= 100 and i["orders"] == 0]
    blind.sort(key=lambda x: x["impressions"], reverse=True)
    for i in blind[:3]:
        problems.append(f"🔴 SKU {i['sku']}: {i['impressions']} показов, 0 заказов. Проверить цену/фото/описание.")

    # 2. Нет остатка, но продаётся (закупить)
    out_of_stock = [i for i in items if i["qty"] == 0 and i["orders"] > 0]
    out_of_stock.sort(key=lambda x: x["orders"], reverse=True)
    for i in out_of_stock[:3]:
        problems.append(f"🟡 SKU {i['sku']}: {i['orders']} заказов, но остаток 0. Срочно закупить.")

    # 3. Отличная конверсия
    stars = [i for i in items if i["c_total"] >= 1.5 and i["orders"] > 0]
    stars.sort(key=lambda x: x["c_total"], reverse=True)
    for i in stars[:2]:
        problems.append(f"🟢 SKU {i['sku']}: отличная конверсия {i['c_total']}%. Держать в наличии.")

    if not problems:
        problems.append("🟢 Критичных проблем в воронке не обнаружено.")

    actions = []
    if blind:
        actions.append(f"По {len(blind)} SKU с показами, но без заказов — проверить карточку (цена, фото). SKU {blind[0]['sku']} — {blind[0]['impressions']} показов.")
    if out_of_stock:
        actions.append(f"Закупить {len(out_of_stock)} SKU, которые продаются, но закончились (SKU {out_of_stock[0]['sku']}).")
    if stars:
        actions.append(f"Масштабировать рекламу на {len(stars)} SKU с конверсией >1.5% (SKU {stars[0]['sku']}).")
    if not actions:
        actions.append("Воронка в норме. Продолжать мониторинг.")

    return main, summary, problems, actions

def _write_sheet(ws, items, dfrom, dto):
    main, summary, problems, actions = _build_report(items)

    values = []
    values.append([f"ВОРОНКА — {dfrom} .. {dto}", "", "", ""])
    values.append(["", "", "", ""])
    values.append(["ГЛАВНОЕ", "", "", ""])
    for line in main:
        values.append([line, "", "", ""])
    values.append(["", "", "", ""])
    values.append(["СВОДКА", "", "", ""])
    for row in summary:
        values.append([row[0], row[1], "", ""])
    values.append(["", "", "", ""])
    values.append(["ПРОБЛЕМЫ", "", "", ""])
    for line in problems:
        values.append([line, "", "", ""])
    values.append(["", "", "", ""])
    values.append(["ЧТО ДЕЛАТЬ", "", "", ""])
    for line in actions:
        values.append([line, "", "", ""])
    values.append(["", "", "", ""])
    values.append(["ДЕТАЛИЗАЦИЯ ПО SKU", "", "", ""])
    values.append(HEADER)
    for i in sorted(items, key=lambda x: x["c_total"], reverse=True):
        values.append([
            i["sku"], i["offer_id"] or "", i["impressions"], i["views"], i["cart"],
            i["orders"], i["buyouts"], i["c1"], i["c2"], i["c3"], i["c4"],
            i["c_total"], i["position"] or "", i["drr"] or "", i["qty"], i["status"],
        ])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")

    format_requests = [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(HEADER)},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": len(values), "startColumnIndex": 0, "endColumnIndex": len(HEADER)},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy"
        }},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 16}, "properties": {"pixelSize": 110}, "fields": "pixelSize"}},
    ]
    ws.spreadsheet.batch_update({"requests": format_requests})

def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    p = argparse.ArgumentParser(description="Лист «Воронка»")
    today = date.today()
    p.add_argument("--from", dest="dfrom", default=(today - timedelta(days=30)).isoformat())
    p.add_argument("--to", dest="dto", default=today.isoformat())
    p.add_argument("--local", action="store_true")
    p.add_argument("--only-in-stock", action="store_true", help="Только SKU с остатком > 0")
    args = p.parse_args(argv)

    items = _load_period(args.dfrom, args.dto, only_in_stock=args.only_in_stock)
    if not items:
        log.warning(f"Нет данных за {args.dfrom}..{args.dto}")
        return 1

    log.info(f"SKU после фильтрации: {len(items)} (only_in_stock={args.only_in_stock})")

    if args.local:
        import csv
        out = __import__("pathlib").Path(APP_DIR) / "out" / f"funnel_{args.dfrom}_{args.dto}.csv"
        out.parent.mkdir(exist_ok=True, parents=True)
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(HEADER)
            for i in sorted(items, key=lambda x: x["c_total"], reverse=True):
                w.writerow([i["sku"], i["offer_id"] or "", i["impressions"], i["views"], i["cart"],
                            i["orders"], i["buyouts"], i["c1"], i["c2"], i["c3"], i["c4"],
                            i["c_total"], i["position"] or "", i["drr"] or "", i["qty"], i["status"]])
        log.info(f"CSV: {out}")
        return 0

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=len(HEADER))

    _write_sheet(ws, items, args.dfrom, args.dto)
    log.info(f"Лист «{SHEET_TITLE}» обновлён.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())