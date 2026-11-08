"""
margin/calc_margin.py — лист "Юнит экономика" в формате Ozon.

Источники:
  - sales_daily           — заказы, отмены, возвраты
  - monthly_realization   — выкупы (=quantity), выручка, комиссия
  - accruals_services     — логистика, агенты, FBO, маркетинг
  - product_cost_history  — себестоимость
  - current_stocks        — FBO/FBS остатки
  - НАСТРОЙКИ B1          — ставка налога, %
  - НАСТРОЙКИ B2/B3       — период от/до
"""
import os
import sys
import sqlite3
import gspread
from google.oauth2.service_account import Credentials

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR   = os.path.dirname(_THIS_DIR)
PNL_DIR   = os.path.join(APP_DIR, "PNL")
if PNL_DIR not in sys.path:
    sys.path.insert(0, PNL_DIR)

import sync_pnl as pnl

DB           = pnl.DB
CREDENTIALS  = pnl.CREDENTIALS
SHEET_ID     = pnl.SHEET_ID
f            = pnl.f

MARGIN_SHEET     = "Юнит экономика"
SETTINGS_SHEET   = "НАСТРОЙКИ"
DEFAULT_TAX_RATE = 7.0

# 29 (LastMileCourier) → в логистику, как у Ozon
SERVICE_GROUPS = {
    "logistics": {32, 59, 98, 16, 17, 38, 39, 29},
    "agents":    {1, 74, 79, 45},
    "fbo":       {46, 71, 76, 12},
    "marketing": {41, 54, 3, 47, 96, 22, 52, 48},
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


def ym(s, is_end):
    if s is None:
        return None
    p = str(s).strip().split("-")
    if len(p) == 1 and len(p[0]) == 4 and p[0].isdigit():
        return f"{p[0]}-12" if is_end else f"{p[0]}-01"
    if len(p) >= 2 and p[0].isdigit():
        return f"{p[0]}-{p[1].zfill(2)}"
    return None


def parse_cli(argv):
    local = "--local" in argv
    fr = to = None
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from" and i + 1 < len(argv):
            fr = argv[i + 1]; i += 2
        elif a == "--to" and i + 1 < len(argv):
            to = argv[i + 1]; i += 2
        elif not a.startswith("--"):
            pos.append(a); i += 1
        else:
            i += 1
    if not fr and not to and pos and pos[0].isdigit() and len(pos[0]) == 4:
        fr = to = pos[0]
    return {"from": ym(fr, False), "to": ym(to, True), "local": local}


def read_settings(sh):
    try:
        ws = sh.worksheet(SETTINGS_SHEET)
        rows = ws.get("B1:B3")
    except Exception as e:
        print(f"[!] {SETTINGS_SHEET}: {e} → defaults")
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
    print(f"[OK] Ставка {tax}%, период {ym(cell(2), False) or '—'} .. {ym(cell(3), True) or '—'}")
    return {"tax_rate": tax, "from": ym(cell(2), False), "to": ym(cell(3), True)}


def load_stocks(con):
    stocks = {}
    for r in con.execute("SELECT sku, offer_id, fbo_present, fbs_present FROM current_stocks"):
        key = r["sku"] if r["sku"] else r["offer_id"]
        if key:
            stocks[key] = (int(f(r["fbo_present"])), int(f(r["fbs_present"])))
    return stocks


def get_month(month, tax_rate, stocks):
    y, m = map(int, month.split("-"))
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d1 = f"{y}-{m:02d}-01"
    d2 = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    skus = {}

    # 1) sales_daily — только заказы / отмены / возвраты
    for r in con.execute("""
        SELECT sku,
               SUM(orders_units)           AS o,
               SUM(cancelled)              AS c,
               SUM(returned_by_order_date) AS rt
        FROM sales_daily
        WHERE date >= ? AND date < ?
        GROUP BY sku
    """, (d1, d2)):
        skus[r["sku"]] = {
            "sku": r["sku"], "offer_id": "", "name": "", "category": "",
            "orders": int(f(r["o"])),
            "cancelled": int(f(r["c"])),
            "returned": int(f(r["rt"])),
            "purchased": 0,
            "seller_price": 0.0, "sale_price": 0.0, "bonus": 0.0,
            "coinvestment": 0.0, "revenue": 0.0, "commission": 0.0,
            "logistics": 0.0, "agents": 0.0, "fbo": 0.0, "marketing": 0.0,
            "cogs": 0.0, "fbo_stock": 0, "fbs_stock": 0,
        }

    # 2) realization — выкупы (quantity), выручка, комиссия
    for r in con.execute("""
        SELECT sku, MAX(offer_id) AS oid, MAX(item_name) AS nm,
               SUM(seller_price) AS sp, SUM(sale_price) AS slp,
               SUM(bonus) AS b, SUM(coinvestment) AS ci,
               SUM(gross_commission) AS gc,
               SUM(quantity) AS purchased
        FROM monthly_realization_rows
        WHERE month = ? AND is_return = 0
        GROUP BY sku
    """, (month,)):
        sku = r["sku"]
        if sku not in skus:
            skus[sku] = {
                "sku": sku, "offer_id": r["oid"] or "", "name": r["nm"] or "",
                "category": "", "orders": 0, "cancelled": 0, "returned": 0,
                "purchased": 0,
                "seller_price": 0.0, "sale_price": 0.0, "bonus": 0.0,
                "coinvestment": 0.0, "revenue": 0.0, "commission": 0.0,
                "logistics": 0.0, "agents": 0.0, "fbo": 0.0, "marketing": 0.0,
                "cogs": 0.0, "fbo_stock": 0, "fbs_stock": 0,
            }
        s = skus[sku]
        s["offer_id"]     = r["oid"] or s["offer_id"]
        s["name"]         = r["nm"]  or s["name"]
        s["purchased"]    = int(r["purchased"] or 0)
        s["seller_price"] = f(r["sp"])
        s["sale_price"]   = f(r["slp"])
        s["bonus"]        = f(r["b"])
        s["coinvestment"] = f(r["ci"])
        s["revenue"]      = f(r["slp"]) + f(r["b"]) + f(r["ci"])
        s["commission"]   = abs(f(r["gc"]))

    # 3) Себестоимость + категория + остатки
    for sku, s in skus.items():
        r = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku = ? AND date_from < ?
            ORDER BY date_from DESC LIMIT 1
        """, (sku, d2)).fetchone()
        s["cogs"] = (f(r[0]) if r and r[0] else 0) * s["purchased"]

        p = con.execute(
            "SELECT category_l1, name, offer_id FROM products WHERE sku = ? LIMIT 1",
            (sku,)
        ).fetchone()
        if p:
            s["category"] = p["category_l1"] or ""
            if not s["offer_id"]: s["offer_id"] = p["offer_id"] or ""
            if not s["name"]:     s["name"]     = p["name"] or ""

        st = stocks.get(sku) or stocks.get(s["offer_id"])
        if st:
            s["fbo_stock"], s["fbs_stock"] = st

    # 4) Услуги
    for row in con.execute("""
        SELECT sku, type_id, SUM(amount) AS t
        FROM accruals_services
        WHERE date >= ? AND date < ?
        GROUP BY sku, type_id
    """, (d1, d2)):
        amt = abs(f(row["t"]))
        if not amt or row["sku"] not in skus:
            continue
        for cat, ids in SERVICE_GROUPS.items():
            if row["type_id"] in ids:
                skus[row["sku"]][cat] += amt
                break

    con.close()
    return skus


def calc_derived(s):
    """Все производные показатели. Порядок важен."""
    d = s["purchased"] or 0

    # Цены (на единицу выкупа)
    s["price_discount"] = (s["seller_price"] / d) if d else 0.0
    s["price_sale"]     = (s["sale_price"]   / d) if d else 0.0

    # Заказы/отмены/возвраты в рублях — через цену со скидкой
    s["orders_rub"]    = s["orders"]    * s["price_discount"]
    s["cancelled_rub"] = s["cancelled"] * s["price_discount"]
    s["returned_rub"]  = s["returned"]  * s["price_discount"]

    # Выкупы %: доля выкупов среди завершённых (выкупы + отмены)
    denom = s["purchased"] + s["cancelled"]
    s["purchases_pct"] = (s["purchased"] / denom * 100.0) if denom else 0.0

    # Расходы на единицу
    s["revenue_unit"] = (s["revenue"]    / d) if d else 0.0
    s["cogs_unit"]    = (s["cogs"]       / d) if d else 0.0
    s["commission_u"] = (s["commission"] / d) if d else 0.0
    s["logistics_u"]  = (s["logistics"]  / d) if d else 0.0

    s["other_mp"]    = s["agents"] + s["fbo"]
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

    s["profit"]   = s["margin"] - s["tax"]
    s["profit_u"] = (s["profit"] / d) if d else 0.0
    s["profit_pct"] = (s["profit"] / s["revenue"] * 100.0) if s["revenue"] else 0.0

    s["markup_pct"] = ((s["price_sale"] - s["cogs_unit"]) / s["cogs_unit"] * 100.0) if s["cogs_unit"] else 0.0
    s["bonus_u"]    = (s["bonus"] / d) if d else 0.0
    s["extras"]     = 0.0
    s["extras_u"]   = 0.0
    return s


def build(start, end, tax_rate):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT month FROM monthly_realization_rows "
        "WHERE month BETWEEN ? AND ? ORDER BY month", (start, end)
    )]
    stocks = load_stocks(con)
    con.close()
    print(f"Месяцы: {months}, остатков в current_stocks: {len(stocks)}")

    all_skus = {}
    SUM_KEYS = ("orders", "purchased", "cancelled", "returned",
                "seller_price", "sale_price", "bonus", "coinvestment",
                "revenue", "commission", "logistics", "agents", "fbo",
                "marketing", "cogs")

    for m in months:
        for sku, s in get_month(m, tax_rate, stocks).items():
            if sku not in all_skus:
                all_skus[sku] = {k: s.get(k, 0) for k in ("sku", "offer_id", "name", "category")}
                for k in SUM_KEYS:
                    all_skus[sku][k] = 0
                all_skus[sku]["fbo_stock"] = s.get("fbo_stock", 0)
                all_skus[sku]["fbs_stock"] = s.get("fbs_stock", 0)
            for k in SUM_KEYS:
                all_skus[sku][k] += s.get(k, 0)
            if s.get("fbo_stock"): all_skus[sku]["fbo_stock"] = s["fbo_stock"]
            if s.get("fbs_stock"): all_skus[sku]["fbs_stock"] = s["fbs_stock"]

    items = []
    for s in all_skus.values():
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
    import re
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
        "range": grid(f"A1:AV1"),
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
    for rng in (f"E2:E{n_rows}", f"H2:J{n_rows}", f"N2:AB{n_rows}",
                f"AC2:AF{n_rows}", f"AG2:AH{n_rows}",
                f"AK2:AL{n_rows}", f"AO2:AP{n_rows}",
                f"AS2:AV{n_rows}"):
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": {"numberFormat": {
                "type": "NUMBER", "pattern": RUB}}},
            "fields": "userEnteredFormat.numberFormat"}})
    for rng in (f"K2:K{n_rows}", f"AI2:AI{n_rows}", f"AJ2:AJ{n_rows}",
                f"AM2:AN{n_rows}", f"AQ2:AR{n_rows}"):
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": {"numberFormat": {
                "type": "NUMBER", "pattern": PCT}}},
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

    from datetime import date
    start = cli["from"] or st["from"] or f"{date.today().year}-01"
    end   = cli["to"]   or st["to"]   or f"{date.today().year}-12"

    print(f"ЮНИТ-ЭКОНОМИКА {start} .. {end}")
    print("=" * 80)

    rows = build(start, end, tax_rate)
    print(f"SKU в таблице: {len(rows) - 1}")

    if cli["local"]:
        import csv
        out = os.path.join(APP_DIR, f"unit_{start}_{end}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerows(rows)
        print(f"[OK] Сохранено: {out}")
        return

    try:
        ws = sh.worksheet(MARGIN_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=MARGIN_SHEET, rows=3000, cols=50)

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    print(f"Записано строк: {len(rows)}")
    apply_format(ws, len(rows))

    print(f"\nГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()