"""
unitka/calc_margin.py — лист "Юнит экономика" за произвольный период.
"""
import os
import re
import sys
import sqlite3
from datetime import date, datetime

import gspread
from google.oauth2.service_account import Credentials

from . import config

DB           = str(config.DB_PATH)
CREDENTIALS  = str(config.CREDENTIALS)
SHEET_ID     = config.SHEET_ID
MARGIN_SHEET = config.MARGIN_SHEET
SETTINGS_SHEET = config.SETTINGS_SHEET
DEFAULT_TAX_RATE = 7.0

SERVICE_GROUPS = {
    "logistics": {16, 17, 28, 29, 30, 32, 38, 39, 42, 43, 44, 45, 59, 73, 98, 12},
    "agents":    {1, 74, 79, 45, 63, 66, 68, 122, 123},
    "fbo":       {21, 46, 71, 76, 84, 85, 86, 97, 108, 109, 111, 131, 132},
    "marketing": {3, 4, 5, 19, 22, 23, 31, 33, 41, 47, 48, 49, 50, 54, 55, 61, 70, 80, 87, 95, 96, 116, 130},
}

HEADER = [
    "Идентификатор товара", "Артикул товара", "Категория",
    "Заказы, шт.", "Заказы в ₽", "Выкупы, шт.", "Отмены, шт.", "Отмены в ₽",
    "Возвраты, шт.", "Возвраты в ₽", "Выкупы в %",
    "FBO остатки, шт.", "FBS остатки, шт.",
    "Цена со скидкой, руб.", "Цена продажи, руб.",
    "Выручка, руб.", "Выручка на ед., руб.",
    "Себестоимость, руб.", "Себестоимость на ед., руб.",
    "Комиссия МП, руб.", "Комиссия МП на ед., руб.",
    "Логистика МП, руб.", "Логистика МП на ед., руб.",
    "Прочие расходы МП, руб.", "Прочие расходы МП на ед., руб.",
    "Реклама, руб.", "Реклама на ед., руб.",
    "ДРР %",
    "Всего расходов на МП, руб.", "Всего расходов на МП на ед., руб.",
    "К выплате, руб.", "К выплате на ед., руб.",
    "Маржа, руб.", "Маржа на ед., руб.", "Маржа в %",
    "Налоговая ставка %",
    "Налоговая база, руб.", "Налоговая база на ед., руб.",
    "Налоги, руб.", "Налоги на ед., руб.",
    "Прибыль, руб.", "Прибыль на ед., руб.", "Прибыль в %",
    "Наценка %",
    "Скидка на МП, руб.", "Скидка на МП на ед., руб.",
    "Доп. расходы, руб.", "Доп. расходы на ед., руб.",
]


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _to_date_start(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    if re.match(r"^\d{4}-\d{2}$", s):
        return s + "-01"
    if re.match(r"^\d{4}$", s):
        return s + "-01-01"
    return None


def _to_date_end(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    if re.match(r"^\d{4}-\d{2}$", s):
        y, m = map(int, s.split("-"))
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        from datetime import date as _d, timedelta as _td
        return (_d(ny, nm, 1) - _td(days=1)).strftime("%Y-%m-%d")
    if re.match(r"^\d{4}$", s):
        return s + "-12-31"
    return None


def parse_cli(argv):
    local = "--local" in argv
    fr = to = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from" and i + 1 < len(argv):
            fr = argv[i + 1]; i += 2
        elif a == "--to" and i + 1 < len(argv):
            to = argv[i + 1]; i += 2
        else:
            i += 1
    return {"from": _to_date_start(fr), "to": _to_date_end(to), "local": local}


def read_settings(sh):
    try:
        ws = sh.worksheet(SETTINGS_SHEET)
        rows = ws.get("B1:B3")
    except Exception as e:
        print(f"[!] {SETTINGS_SHEET}: {e} -> defaults")
        return {"tax_rate": DEFAULT_TAX_RATE, "from": None, "to": None}

    def cell(r):
        if len(rows) >= r and rows[r - 1] and rows[r - 1][0] not in (None, ""):
            return rows[r - 1][0]
        return None

    tax = DEFAULT_TAX_RATE
    raw = cell(1)
    if raw is not None:
        try:
            tax = float(str(raw).replace("%", "").replace(",", ".").strip())
        except ValueError:
            pass
    print(f"[OK] Ставка {tax}%, период "
          f"{_to_date_start(cell(2)) or '—'} .. {_to_date_end(cell(3)) or '—'}")
    return {"tax_rate": tax,
            "from": _to_date_start(cell(2)),
            "to":   _to_date_end(cell(3))}


def load_stocks(con):
    stocks = {}
    for r in con.execute("SELECT sku, offer_id, fbo_present, fbs_present FROM current_stocks"):
        key = r["sku"] if r["sku"] else r["offer_id"]
        if key:
            stocks[key] = (int(_f(r["fbo_present"])), int(_f(r["fbs_present"])))
    return stocks


def load_period(con, start, end, stocks):
    skus = {}

    def ensure(sku):
        if sku not in skus:
            skus[sku] = {
                "sku": sku, "offer_id": "", "name": "", "category": "",
                "orders": 0, "cancelled": 0, "returned": 0, "purchased": 0,
                "seller_price": 0.0, "sale_price": 0.0, "bonus": 0.0,
                "coinvestment": 0.0, "revenue": 0.0, "commission": 0.0,
                "logistics": 0.0, "agents": 0.0, "fbo": 0.0,
                "marketing": 0.0, "other": 0.0,
                "cogs": 0.0, "fbo_stock": 0, "fbs_stock": 0,
            }
        return skus[sku]

    # orders/cancelled/returned — из postings_daily (API + XLSX-отчёт),
    # НЕ из sales_daily. Одна строка = SKU внутри отправления.
    # purchased_delivered_only — считаем выкупы только по статусу delivered,
    # а не orders-cancelled-returned (иначе попадают заказы в пути).
    for r in con.execute("""
        SELECT sku,
               SUM(quantity) AS o,
               SUM(CASE WHEN is_cancelled=1 THEN quantity ELSE 0 END) AS c,
               SUM(CASE WHEN is_returned =1 THEN quantity ELSE 0 END) AS rt,
               SUM(CASE WHEN lower(status)='delivered' THEN quantity ELSE 0 END) AS dlv
        FROM postings_daily
        WHERE date BETWEEN ? AND ?
        GROUP BY sku
    """, (start, end)):
        try:
            sku_key = int(r["sku"])
        except (TypeError, ValueError):
            sku_key = r["sku"]
        s = ensure(sku_key)
        s["orders"]    = int(_f(r["o"]))
        s["cancelled"] = int(_f(r["c"]))
        s["returned"]  = int(_f(r["rt"]))
        s["purchased"] = int(_f(r["dlv"]))

    for r in con.execute("""
        SELECT sku,
               SUM(CASE WHEN seller_price > 0 THEN quantity ELSE 0 END) - SUM(CASE WHEN seller_price < 0 THEN quantity ELSE 0 END) AS q,
               SUM(seller_price)  AS sp,
               SUM(sale_price)    AS slp,
               SUM(bonus)         AS b,
               SUM(coinvestment)  AS ci,
               SUM(commission)    AS cm,
               SUM(delivery_total) AS dl
        FROM realization_daily
        WHERE date BETWEEN ? AND ?
          AND (seller_price != 0 OR commission != 0)
        GROUP BY sku
    """, (start, end)):
        s = ensure(r["sku"])
        s["seller_price"] = _f(r["sp"])
        s["sale_price"]   = _f(r["slp"])
        s["bonus"]        = _f(r["b"])
        s["coinvestment"] = _f(r["ci"])
        s["revenue"]      = s["sale_price"] + s["bonus"] + s["coinvestment"]
        s["commission"]   = abs(_f(r["cm"]))

    for r in con.execute("""
        SELECT sku, type_id, SUM(amount) AS t
        FROM accrual_sku_daily
        WHERE date BETWEEN ? AND ?
        GROUP BY sku, type_id
    """, (start, end)):
        amt = abs(_f(r["t"]))
        if not amt or r["sku"] not in skus:
            continue
        tid = r["type_id"]
        placed = False
        for cat, ids in SERVICE_GROUPS.items():
            if tid in ids:
                skus[r["sku"]][cat] += amt
                placed = True
                break
        if not placed:
            skus[r["sku"]]["other"] += amt

    rows = con.execute("""
        SELECT a.date, a.posting_number, a.type_id, a.amount,
               r.sku, r.seller_price AS sku_amount
        FROM accrual_non_item_daily a
        JOIN realization_daily r
          ON r.date = a.date AND r.posting_number = a.posting_number
        WHERE a.date BETWEEN ? AND ?
          AND (r.seller_price != 0 OR r.commission != 0)
    """, (start, end)).fetchall()

    posting_total = {}
    for r in rows:
        key = (r["date"], r["posting_number"])
        posting_total[key] = posting_total.get(key, 0.0) + _f(r["sku_amount"])

    for r in rows:
        key = (r["date"], r["posting_number"])
        total = posting_total.get(key, 0.0)
        if not total or r["sku"] not in skus:
            continue
        share = _f(r["sku_amount"]) / total
        amt = abs(_f(r["amount"])) * share
        tid = r["type_id"]
        placed = False
        for cat, ids in SERVICE_GROUPS.items():
            if tid in ids:
                skus[r["sku"]][cat] += amt
                placed = True
                break
        if not placed:
            skus[r["sku"]]["other"] += amt

    for sku, s in skus.items():
        row = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku = ? AND date_from <= ?
            ORDER BY date_from DESC LIMIT 1
        """, (sku, end)).fetchone()
        s["cogs"] = (_f(row[0]) if row and row[0] else 0.0) * s["purchased"]

        p = con.execute(
            "SELECT category_l1, name, offer_id FROM products WHERE sku = ? LIMIT 1",
            (sku,)).fetchone()
        if p:
            s["category"] = p["category_l1"] or ""
            if not s["offer_id"]: s["offer_id"] = p["offer_id"] or ""
            if not s["name"]:     s["name"]     = p["name"] or ""

        st = stocks.get(sku) or stocks.get(s["offer_id"])
        if st:
            s["fbo_stock"], s["fbs_stock"] = st

    return skus


def calc_derived(s):
    d = s["purchased"] or 0

    s["price_discount"] = (s["seller_price"] / d) if d else 0.0
    s["price_sale"]     = (s["sale_price"]   / d) if d else 0.0

    s["orders_rub"]    = s["orders"]    * s["price_discount"]
    s["cancelled_rub"] = s["cancelled"] * s["price_discount"]
    s["returned_rub"]  = s["returned"]  * s["price_discount"]

    denom = s["purchased"] + s["cancelled"]
    s["purchases_pct"] = (s["purchased"] / denom * 100.0) if denom else 0.0

    s["revenue_unit"] = (s["revenue"]    / d) if d else 0.0
    s["cogs_unit"]    = (s["cogs"]       / d) if d else 0.0
    s["commission_u"] = (s["commission"] / d) if d else 0.0
    s["logistics_u"]  = (s["logistics"]  / d) if d else 0.0

    s["other_mp"]    = s["agents"] + s["fbo"] + s["other"]
    s["other_mp_u"]  = (s["other_mp"] / d) if d else 0.0
    s["marketing_u"] = (s["marketing"] / d) if d else 0.0

    s["total_mp"]   = s["commission"] + s["logistics"] + s["other_mp"] + s["marketing"]
    s["total_mp_u"] = (s["total_mp"] / d) if d else 0.0
    s["drr_pct"]    = (s["marketing"] / s["revenue"] * 100.0) if s["revenue"] else 0.0

    s["payout"]   = s["revenue"] - s["total_mp"]
    s["payout_u"] = (s["payout"] / d) if d else 0.0

    s["margin"]   = s["revenue"] - s["cogs"] - s["total_mp"]
    s["margin_u"] = (s["margin"] / d) if d else 0.0
    s["margin_pct"] = (s["margin"] / s["revenue"] * 100.0) if s["revenue"] else 0.0

    s["tax_base"]   = s["sale_price"]
    s["tax_base_u"] = (s["tax_base"] / d) if d else 0.0
    s["tax"]        = s["tax_base"] * s["tax_rate"] / 100.0
    s["tax_u"]      = (s["tax"] / d) if d else 0.0

    s["profit"]     = s["margin"] - s["tax"]
    s["profit_u"]   = (s["profit"] / d) if d else 0.0
    s["profit_pct"] = (s["profit"] / s["revenue"] * 100.0) if s["revenue"] else 0.0

    s["markup_pct"] = ((s["price_sale"] - s["cogs_unit"]) / s["cogs_unit"] * 100.0) \
                       if s["cogs_unit"] else 0.0
    s["bonus_u"]    = (s["bonus"] / d) if d else 0.0
    s["extras"]     = 0.0
    s["extras_u"]   = 0.0
    return s


def build(start, end, tax_rate):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    stocks = load_stocks(con)
    print(f"Период: {start} .. {end}, остатков в current_stocks: {len(stocks)}")

    data = load_period(con, start, end, stocks)
    con.close()

    items = []
    for s in data.values():
        s["tax_rate"] = tax_rate
        s = calc_derived(s)
        if s["orders"] > 0 or s["purchased"] > 0:
            items.append(s)

    items.sort(key=lambda x: x["profit"], reverse=True)

    rows = [HEADER]
    for s in items:
        rows.append([
            s["sku"], s["offer_id"], s["category"],
            s["orders"], round(s["orders_rub"], 2),
            s["purchased"], s["cancelled"], round(s["cancelled_rub"], 2),
            s["returned"], round(s["returned_rub"], 2),
            round(s["purchases_pct"], 2),
            s["fbo_stock"], s["fbs_stock"],
            round(s["price_discount"], 2), round(s["price_sale"], 2),
            round(s["revenue"], 2), round(s["revenue_unit"], 2),
            round(s["cogs"], 2), round(s["cogs_unit"], 2),
            round(s["commission"], 2), round(s["commission_u"], 2),
            round(s["logistics"], 2), round(s["logistics_u"], 2),
            round(s["other_mp"], 2), round(s["other_mp_u"], 2),
            round(s["marketing"], 2), round(s["marketing_u"], 2),
            round(s["drr_pct"], 2),
            round(s["total_mp"], 2), round(s["total_mp_u"], 2),
            round(s["payout"], 2), round(s["payout_u"], 2),
            round(s["margin"], 2), round(s["margin_u"], 2), round(s["margin_pct"], 2),
            round(tax_rate, 2),
            round(s["tax_base"], 2), round(s["tax_base_u"], 2),
            round(s["tax"], 2), round(s["tax_u"], 2),
            round(s["profit"], 2), round(s["profit_u"], 2), round(s["profit_pct"], 2),
            round(s["markup_pct"], 2),
            round(s["bonus"], 2), round(s["bonus_u"], 2),
            round(s["extras"], 2), round(s["extras_u"], 2),
        ])
    return rows


def apply_format(ws, n_rows):
    sid = ws.id
    reqs = []

    def grid(rng):
        m = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
        c1, r1, c2, r2 = m.groups()
        def col(c):
            n = 0
            for ch in c:
                n = n * 26 + (ord(ch) - ord("A") + 1)
            return n - 1
        return {"sheetId": sid,
                "startRowIndex": int(r1) - 1, "endRowIndex": int(r2),
                "startColumnIndex": col(c1), "endColumnIndex": col(c2) + 1}

    GREY = {"red": 0.93, "green": 0.93, "blue": 0.93}
    NAVY = {"red": 0.10, "green": 0.18, "blue": 0.35}

    reqs.append({"repeatCell": {
        "range": grid("A1:AV1"),
        "cell": {"userEnteredFormat": {
            "backgroundColor": GREY,
            "textFormat": {"foregroundColor": NAVY, "bold": True, "fontSize": 10},
            "horizontalAlignment": "CENTER", "wrapStrategy": "WRAP"}},
        "fields": "userEnteredFormat"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 60}, "fields": "pixelSize"}})

    RUB = '#,##0.00" ₽"'
    PCT = '0.00" %"'
    for rng in (f"E2:E{n_rows}", f"H2:H{n_rows}", f"J2:J{n_rows}", f"N2:AA{n_rows}",
                f"AC2:AF{n_rows}", f"AG2:AH{n_rows}",
                f"AK2:AL{n_rows}", f"AM2:AN{n_rows}", f"AO2:AP{n_rows}", f"AS2:AV{n_rows}"):
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": {"numberFormat": {
                "type": "NUMBER", "pattern": RUB}}},
            "fields": "userEnteredFormat.numberFormat"}})
    for rng in (f"K2:K{n_rows}", f"AB2:AB{n_rows}", f"AI2:AI{n_rows}", f"AJ2:AJ{n_rows}", f"AQ2:AR{n_rows}"):
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": {"numberFormat": {
                "type": "NUMBER", "pattern": PCT}}},
            "fields": "userEnteredFormat.numberFormat"}})

    # Явно сбрасываем формат колонки I — иначе остаётся ₽ от прошлых запусков
    reqs.append({"repeatCell": {
    "range": grid(f"I2:I{n_rows}"),
    "cell": {"userEnteredFormat": {"numberFormat": {
        "type": "NUMBER", "pattern": "0"}}},
    "fields": "userEnteredFormat.numberFormat"}})

    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount"}})

    ws.spreadsheet.batch_update({"requests": reqs})


def main():
    cli = parse_cli(sys.argv[1:])
    print("=" * 80)

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    st = read_settings(sh)
    tax_rate = st["tax_rate"]

    start = cli["from"] or st["from"] or f"{date.today().year}-01-01"
    end   = cli["to"]   or st["to"]   or f"{date.today().year}-12-31"

    print(f"ЮНИТ-ЭКОНОМИКА {start} .. {end}")
    print("=" * 80)

    rows = build(start, end, tax_rate)
    print(f"SKU в таблице: {len(rows) - 1}")

    if cli["local"]:
        import csv
        out = os.path.join(str(config.PROJECT), f"unit_{start}_{end}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerows(rows)
        print(f"[OK] Сохранено: {out}")
        for row in rows[:6]:
            print("  " + " | ".join(str(x) for x in row[:8]))
        return

    try:
        ws = sh.worksheet(MARGIN_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=MARGIN_SHEET, rows=3000, cols=50)

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    print(f"Записано строк: {len(rows)}")
    apply_format(ws, len(rows))

    import os as _os
    if not _os.environ.get("UNITKA_QUIET"):
        print(f"\nГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
        print("=" * 80)


if __name__ == "__main__":
    main()
