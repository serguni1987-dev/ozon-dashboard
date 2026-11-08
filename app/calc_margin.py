"""
margin/calc_margin.py — лист МАРЖА: юнит-экономика по SKU.

Формула:
    Выручка SKU (sale_price + bonus + coinvestment, is_return=0)
  − Себестоимость (cost_price × quantity)
  − Комиссия Ozon (gross_commission)
  − Логистика        (type_id 32, 59, 98, 16, 17, 38, 39 из accruals_services, по sku)
  − Услуги агентов   (type_id 1, 74, 79, 29, 45)
  − Услуги FBO       (type_id 46, 71, 76, 12)
  − Маркетинг        (type_id 41, 54, 3, 47, 96, 22, 52, 48)
  − Налог            (база × ставка%)
  = МАРЖА SKU

Ставка налога берётся из НАСТРОЙКИ!B2.
База налога — как в P&L: sale_price + coinvestment (без bonus).
"""
import os
import sys
import sqlite3
import gspread
from google.oauth2.service_account import Credentials

# ── Импорт констант и CATEGORY_MAP из PNL ─────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR   = os.path.dirname(_THIS_DIR)
PNL_DIR   = os.path.join(APP_DIR, "PNL")
if PNL_DIR not in sys.path:
    sys.path.insert(0, PNL_DIR)

import sync_pnl as pnl

DB           = pnl.DB
CREDENTIALS  = pnl.CREDENTIALS
SHEET_ID     = pnl.SHEET_ID
CATEGORY_MAP = pnl.CATEGORY_MAP
f            = pnl.f

# ── Настройки ─────────────────────────────────────────────────
DEFAULT_TAX_RATE = 6.0
MARGIN_SHEET     = "МАРЖА"
SETTINGS_SHEET   = "НАСТРОЙКИ"
SETTINGS_CELL    = "B2"
NO_SKU_KEY       = -1          # псевдо-SKU для начислений без привязки

# Группы сервисов по type_id
SERVICE_GROUPS = {
    "logistics": {32, 59, 98, 16, 17, 38, 39},
    "agents":    {1, 74, 79, 29, 45},
    "fbo":       {46, 71, 76, 12},
    "marketing": {41, 54, 3, 47, 96, 22, 52, 48},
}


# ── Ставка налога ─────────────────────────────────────────────
def get_tax_rate(sh):
    try:
        ws = sh.worksheet(SETTINGS_SHEET)
        raw = ws.acell(SETTINGS_CELL).value
        if raw is None or str(raw).strip() == "":
            print(f"[i] {SETTINGS_SHEET}!{SETTINGS_CELL} пусто → {DEFAULT_TAX_RATE}%")
            return DEFAULT_TAX_RATE
        rate = float(str(raw).replace("%", "").replace(",", ".").strip())
        print(f"[OK] Ставка налога = {rate}%")
        return rate
    except gspread.WorksheetNotFound:
        print(f"[!] Листа {SETTINGS_SHEET} нет → {DEFAULT_TAX_RATE}%")
        return DEFAULT_TAX_RATE
    except Exception as e:
        print(f"[!] Не прочитал ставку ({e}) → {DEFAULT_TAX_RATE}%")
        return DEFAULT_TAX_RATE


# ── Расчёт по месяцу ──────────────────────────────────────────
def get_margin_for_month(month, tax_rate):
    y, m = map(int, month.split("-"))
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d1 = f"{y}-{m:02d}-01"
    d2 = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # 1) Выручка + комиссия по SKU
    skus = {}
    for r in con.execute("""
        SELECT sku,
               MAX(offer_id)         AS offer_id,
               MAX(item_name)        AS item_name,
               SUM(sale_price)       AS sale_price,
               SUM(bonus)            AS bonus,
               SUM(coinvestment)     AS coinvestment,
               SUM(gross_commission) AS commission,
               SUM(quantity)         AS qty
        FROM monthly_realization_rows
        WHERE month = ? AND is_return = 0
        GROUP BY sku
    """, (month,)):
        skus[r["sku"]] = {
            "sku":          r["sku"],
            "offer_id":     r["offer_id"] or "",
            "name":         r["item_name"] or "",
            "qty":          int(r["qty"] or 0),
            "sale_price":   f(r["sale_price"]),
            "bonus":        f(r["bonus"]),
            "coinvestment": f(r["coinvestment"]),
            "revenue":      f(r["sale_price"]) + f(r["bonus"]) + f(r["coinvestment"]),
            "commission":   abs(f(r["commission"])),
            "logistics":    0.0,
            "agents":       0.0,
            "fbo":          0.0,
            "marketing":    0.0,
            "cogs":         0.0,
            "tax":          0.0,
            "margin":       0.0,
            "margin_pct":   0.0,
        }

    # 2) Себестоимость
    for sku, s in skus.items():
        r = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku = ? AND date_from < ?
            ORDER BY date_from DESC LIMIT 1
        """, (sku, d2)).fetchone()
        cost = f(r[0]) if r and r[0] else 0
        s["cogs"] = cost * s["qty"]

    # 3) Услуги по SKU из accruals_services
    no_sku_acc = {cat: 0.0 for cat in SERVICE_GROUPS}
    for row in con.execute("""
        SELECT sku, type_id, SUM(amount) AS total
        FROM accruals_services
        WHERE date >= ? AND date < ?
        GROUP BY sku, type_id
    """, (d1, d2)):
        amt = abs(f(row["total"]))
        if amt == 0:
            continue
        cat = None
        for c, ids in SERVICE_GROUPS.items():
            if row["type_id"] in ids:
                cat = c
                break
        if cat is None:
            continue    # не входит в юнит-экономику (например, ItemCompensation)

        sku = row["sku"]
        if sku is not None and sku in skus:
            skus[sku][cat] += amt
        else:
            no_sku_acc[cat] += amt

    con.close()

    # 4) Налог и маржа
    for s in skus.values():
        # база как в P&L: sale_price + coinvestment
        tax_base = s["sale_price"] + s["coinvestment"]
        s["tax"] = tax_base * tax_rate / 100.0
        s["margin"] = (
            s["revenue"] - s["cogs"] - s["commission"]
            - s["logistics"] - s["agents"] - s["fbo"]
            - s["marketing"] - s["tax"]
        )
        s["margin_pct"] = (s["margin"] / s["revenue"] * 100.0) if s["revenue"] else 0.0

    # Псевдо-SKU "(без SKU)" — если есть начисления без привязки
    if any(v > 0 for v in no_sku_acc.values()):
        total = sum(no_sku_acc.values())
        skus[NO_SKU_KEY] = {
            "sku":          NO_SKU_KEY,
            "offer_id":     "(без SKU)",
            "name":         "Начисления, не привязанные к товару",
            "qty":          0,
            "sale_price":   0.0,
            "bonus":        0.0,
            "coinvestment": 0.0,
            "revenue":      0.0,
            "commission":   0.0,
            "logistics":    no_sku_acc["logistics"],
            "agents":       no_sku_acc["agents"],
            "fbo":          no_sku_acc["fbo"],
            "marketing":    no_sku_acc["marketing"],
            "cogs":         0.0,
            "tax":          0.0,
            "margin":       -total,
            "margin_pct":   0.0,
        }

    return skus


# ── Сборка по году ────────────────────────────────────────────
def build_table(year, tax_rate):
    con = sqlite3.connect(DB)
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT month FROM monthly_realization_rows "
        "WHERE month LIKE ? ORDER BY month", (f"{year}-%",)
    )]
    con.close()
    print(f"Месяцы: {months}")

    all_skus = {}

    def _zero(sku_obj):
        return {k: sku_obj.get(k, 0) for k in (
            "qty", "sale_price", "bonus", "coinvestment", "revenue",
            "cogs", "commission", "logistics", "agents", "fbo",
            "marketing", "tax", "margin"
        )}

    for month in months:
        for sku, s in get_margin_for_month(month, tax_rate).items():
            if sku not in all_skus:
                all_skus[sku] = {
                    "sku":      s["sku"],
                    "offer_id": s["offer_id"],
                    "name":     s["name"],
                    **_zero(s),
                }
            for k in ("qty", "sale_price", "bonus", "coinvestment", "revenue",
                      "cogs", "commission", "logistics", "agents", "fbo",
                      "marketing", "tax", "margin"):
                all_skus[sku][k] += s.get(k, 0)

    # Проценты и категория
    for s in all_skus.values():
        s["margin_pct"] = (s["margin"] / s["revenue"] * 100.0) if s["revenue"] else 0.0
        if s["revenue"] == 0 and s["margin"] < 0:
            s["category"] = "⚪ БЕЗ ВЫРУЧКИ"
        elif s["margin_pct"] < 0:
            s["category"] = "🔴 УБЫТОЧНЫЙ"
        elif s["margin_pct"] < 10:
            s["category"] = "🟡 НИЖЕ НОРМЫ"
        else:
            s["category"] = "🟢 НОРМА"

    # Сортировка: убыточные наверх, потом по марже %
    items = sorted(all_skus.values(), key=lambda x: (x["margin_pct"], x["margin"]))

    header = [
        "Offer ID", "Название", "SKU", "Кол-во",
        "Выручка", "Себест", "Комиссия Ozon", "Логистика",
        "Агенты", "FBO", "Маркетинг", "Налог ₽",
        "Маржа ₽", "Маржа %", "Категория",
    ]

    rows = [header]
    for s in items:
        rows.append([
            s["offer_id"], s["name"], s["sku"], int(s["qty"]),
            round(s["revenue"], 2),    round(s["cogs"], 2),
            round(s["commission"], 2), round(s["logistics"], 2),
            round(s["agents"], 2),     round(s["fbo"], 2),
            round(s["marketing"], 2),  round(s["tax"], 2),
            round(s["margin"], 2),     round(s["margin_pct"], 2),
            s["category"],
        ])
    return rows


# ── Форматирование ────────────────────────────────────────────
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

    def fmt(rng, bg=None, fg=None, bold=False, size=10, align=None):
        cf = {}
        if bg: cf["backgroundColor"] = bg
        tf = {}
        if fg:    tf["foregroundColor"] = fg
        if bold:  tf["bold"] = True
        if size:  tf["fontSize"] = size
        if tf:    cf["textFormat"] = tf
        if align: cf["horizontalAlignment"] = align
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": cf},
            "fields": "userEnteredFormat"}})

    WHITE = {"red": 1,    "green": 1,    "blue": 1}
    BLUE  = {"red": 0.10, "green": 0.45, "blue": 0.91}

    fmt("A1:O1", bg=BLUE, fg=WHITE, bold=True, size=11, align="CENTER")

    # Числа
    RUB = '#,##0.00" ₽";[Red]-#,##0.00" ₽"'
    PCT = '0.00" %"'
    reqs.append({"repeatCell": {
        "range": grid(f"E2:M{n_rows}"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": RUB}}},
        "fields": "userEnteredFormat.numberFormat"}})
    reqs.append({"repeatCell": {
        "range": grid(f"N2:N{n_rows}"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": PCT}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # Условное форматирование колонки O по значению — 3 правила
    GREEN_BG = {"red": 0.85, "green": 0.96, "blue": 0.85}
    YEL_BG   = {"red": 1.00, "green": 0.95, "blue": 0.80}
    RED_BG   = {"red": 0.99, "green": 0.88, "blue": 0.88}
    GREY_BG  = {"red": 0.93, "green": 0.93, "blue": 0.93}

    for text, bg in (("🔴", RED_BG), ("🟡", YEL_BG),
                     ("🟢", GREEN_BG), ("⚪", GREY_BG)):
        reqs.append({"addConditionalFormatRule": {
            "rule": {
                "ranges": [grid(f"O2:O{n_rows}")],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_CONTAINS",
                        "values": [{"userEnteredValue": text}],
                    },
                    "format": {"backgroundColor": bg},
                },
            },
            "index": 0,
        }})

    # Ширины
    widths = [130, 340, 100, 70, 115, 110, 115,
              95, 95, 95, 95, 95, 115, 90, 150]
    for i, w in enumerate(widths):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount"}})

    ws.spreadsheet.batch_update({"requests": reqs})


# ── Точка входа ───────────────────────────────────────────────
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(args[0]) if args else 2026
    local = "--local" in sys.argv

    print("=" * 80)
    print(f"ЮНИТ-ЭКОНОМИКА ЗА {year}  {'(локально)' if local else ''}")
    print("=" * 80)

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    tax_rate = get_tax_rate(sh)
    rows = build_table(year, tax_rate)
    print(f"SKU в таблице: {len(rows) - 1}")

    if local:
        import csv
        out = os.path.join(APP_DIR, f"margin_{year}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerows(rows)
        print(f"[OK] Сохранено: {out}")
        return

    try:
        ws = sh.worksheet(MARGIN_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=MARGIN_SHEET, rows=2000, cols=20)

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    print(f"Записано строк: {len(rows)}")

    apply_format(ws, len(rows))

    print(f"\nГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()