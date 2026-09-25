"""
sync_pnl.py - лист P&L: год по месяцам.
"""
import os
import re
import sqlite3
import sys
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(APP_DIR, "ozon.db")
CREDENTIALS = os.path.join(APP_DIR, "credentials.json")
TAX_RATE = 0.15

_sync = open(os.path.join(APP_DIR, "sheets_sync.py"), encoding="utf-8").read()
SHEET_ID = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', _sync).group(1)

CATEGORY_MAP = {
    # фулфилмент
    32: "Логистика",  77: "Логистика",
    59: "Логистика", 71: "Услуги FBO", 45: "Обратная логистика",
    29: "Последняя миля", 98: "Последняя миля",
    25: "ItemCompensation",
    12: "Услуги FBO", 16: "Логистика", 17: "Логистика", 38: "Обработка, сборка",
    39: "Обработка, сборка", 78: "Обработка, сборка", 79: "Обработка, сборка",
    # маркетинг — РАСШИРЕНО
    41: "Реклама PPC",        # PayPerClick
    54: "Продвижение",         # Promotion
    74: "Звёзды",              # StarsMembership
    3:  "Бренд-комиссия",      # BrandCommission
    47: "Отзывы",              # PointsForReviews
    96: "Отзывы",              # AcceleratedReviewCollection
    # агенты
    1:  "Услуги агентов", 18: "Услуги агентов",
    20: "Услуги агентов", 22: "Услуги агентов",
    # FBO
    46: "Услуги FBO", 76: "Услуги FBO",
    # другие
    14: "Другие услуги", 15: "Другие услуги", 48: "Другие услуги",
    52: "Другие услуги", 93: "Другие услуги", 94: "Другие услуги",
    # прочие
    6: "Прочие", 9: "Прочие", 40: "Прочие",
}




MONTHS = ["янв", "фев", "мар", "апр", "май", "июн",
          "июл", "авг", "сен", "окт", "ноя", "дек"]
QUARTERS = ["1 кв", "2 кв", "3 кв", "4 кв"]


def f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def get_pnl_for_month(month):
    y, m = month.split("-")
    y, m = int(y), int(m)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d1 = f"{y}-{m:02d}-01"
    d2 = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Доходы из realization
    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    sale_price = f(r["slp"])
    bonus = f(r["bonus"])
    coinv = f(r["coinv"])
    commission = abs(f(r["comm"]))

    # Заказы
    r2 = con.execute("""
        SELECT SUM(orders_units) AS orders FROM sales_daily
        WHERE date >= ? AND date < ?
    """, (d1, d2)).fetchone()
    orders = int(r2["orders"] or 0)

    # Услуги из accruals_services
    cats = {}
    for row in con.execute("""
        SELECT type_id, SUM(amount) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (d1, d2)):
        cat = CATEGORY_MAP.get(row["type_id"], "Без категории")
        cats[cat] = cats.get(cat, 0) + abs(f(row["total"]))

    # Себестоимость: delivered × cost по SKU из realization
    cogs = 0.0

    # Основной путь: sales_daily (есть с июня)
    real_skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
    )]
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])

    # Fallback: если sales_daily пусто (янв-май) — через accruals POSTING
    if cogs == 0:
        # Fallback: каждый unit_number — +1 если продажа, -1 если возврат
        for row in con.execute("""
            SELECT sku, SUM(sign) AS units
            FROM (
                SELECT DISTINCT a.sku, a.unit_number,
                       CASE WHEN a.seller_price > 0 THEN 1
                            WHEN a.seller_price < 0 THEN -1
                            ELSE 0 END AS sign
                FROM accruals a
                WHERE a.date >= ? AND a.date < ?
                  AND a.accrued_category = 'POSTING'
                  AND a.seller_price IS NOT NULL
                  AND a.sku IS NOT NULL
            )
            GROUP BY sku
        """, (d1, d2)):
            sku = row[0]
            units = int(row[1] or 0)
            if units == 0:
                continue
            r = con.execute("SELECT cost_price FROM products WHERE sku = ?", (sku,)).fetchone()
            cost = f(r[0]) if r else 0
            if cost > 0:
                cogs += units * cost

    con.close()

    revenue = sale_price + bonus + coinv
    ads = cats.get("Реклама", 0)
    services_no_ads = sum(v for k, v in cats.items()
                       if k not in ("Реклама", "ItemCompensation"))
    expenses_no_ads = commission + services_no_ads - cats.get("ItemCompensation", 0)
    margin = revenue - expenses_no_ads - ads - cogs
    tax_base = revenue - bonus
    tax = tax_base * TAX_RATE
    net = margin - tax
    roi = (net / cogs * 100) if cogs else 0

    return {
        "orders": orders, "bonus": bonus, "revenue": revenue,
        "sale_price": sale_price, "coinv": coinv, "commission": commission,
        "cogs": cogs,
        "fulfil_logistics":  cats.get("Логистика", 0),
        "fulfil_reverse":    cats.get("Обратная логистика", 0),
        "fulfil_lastmile":   cats.get("Последняя миля", 0),
        "fulfil_processing": cats.get("Обработка, сборка", 0),
        "fulfil_total":     (cats.get("Логистика", 0) + cats.get("Обратная логистика", 0)
                              + cats.get("Последняя миля", 0) + cats.get("Обработка, сборка", 0)),
        "ppc":   cats.get("Реклама PPC", 0),
        "promo": cats.get("Продвижение", 0),
        "stars": cats.get("Звёзды", 0),
        "brand": cats.get("Бренд-комиссия", 0),
        "reviews": cats.get("Отзывы", 0),
        "market_total": (cats.get("Реклама PPC", 0) + cats.get("Продвижение", 0)
                         + cats.get("Звёзды", 0) + cats.get("Бренд-комиссия", 0)
                         + cats.get("Отзывы", 0)),
        "agents": cats.get("Услуги агентов", 0),
        "fbo": cats.get("Услуги FBO", 0),
        "other": cats.get("Другие услуги", 0),
        "misc": cats.get("Прочие", 0), "ads": ads,
        "expenses_no_ads": expenses_no_ads,
        "expenses_total": expenses_no_ads + ads,
        "margin": margin, "tax_base": tax_base, "tax": tax, "net": net, "roi": roi,
    }



def get_all_months():
    con = sqlite3.connect(DB)
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT month FROM monthly_realization_rows ORDER BY month"
    )]
    con.close()
    return months


def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s



def add_calc_formulas(rows):
    """Строки:
       36 = SUM(37:40)  Операционные всего
       37-40           Операционные подстроки (ручной ввод C:N)
       42 = 34 - 36    EBITDA
       46 = 42 + 44    Чистая (44 — налог, уже со знаком минус)
       47 = -46/32*100 ROI
    """
    COL_YEAR = 2
    COL_MONTH_1 = 3
    COL_Q1 = 15

    def year_sum(row_idx):
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        r = row_idx + 1
        rows[row_idx][COL_YEAR - 1] = f"=SUM({c1}{r}:{c12}{r})"

    def quarter_sums(row_idx):
        r = row_idx + 1
        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(COL_MONTH_1 + m1 - 1)
            cB = col_letter(COL_MONTH_1 + m2 - 1)
            rows[row_idx][COL_Q1 + q - 1 - 1] = f"=SUM({cA}{r}:{cB}{r})"

    for ri in (36, 37, 38, 39):
        year_sum(ri); quarter_sums(ri)

    for m in range(1, 13):
        c = col_letter(COL_MONTH_1 + m - 1)
        idx = COL_MONTH_1 + m - 1 - 1
        rows[35][idx] = f"=SUM({c}37:{c}40)"
    year_sum(35); quarter_sums(35)

    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[41][idx] = f"={col}34-{col}36"
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[45][idx] = f"={col}42+{col}44"
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[46][idx] = f"=IF({col}32=0;0;-{col}46/{col}32*100)"


def build_table(year=2026):
    all_months = [m for m in get_all_months() if m.startswith(str(year))]
    by_month = {m: get_pnl_for_month(m) for m in all_months}

    COL_YEAR = 2
    COL_MONTH_1 = 3
    COL_Q1 = 15

    def mcol(mn):
        return COL_MONTH_1 + (mn - 1)

    def qcol(q):
        return COL_Q1 + (q - 1)

    rows = []
    rows.append(["Отчёт о прибылях и убытках OZON"] + [""] * 18)

    row2 = [""] * 19
    row2[1] = f"Всего за {year}"
    for i, name in enumerate(MONTHS):
        row2[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        row2[qcol(i + 1) - 1] = name
    rows.append(row2)

    lines = [
        ("Заказы (справочно)", "orders"),
        ("Начислено баллов", "bonus"),
        ("Всего к начислению (Отчёт о реализации)", "revenue"),
        ("Сумма Отчёта о реализации", "sale_price"),
        ("", None),
        ("ДОХОДЫ", "revenue"),
        ("  Выручка за вычетом возвратов", "sale_price"),
        ("  Баллы за скидки", "bonus"),
        ("  Программы партнёров", "coinv"),
        ("  Компенсации", None),
        ("", None),
        ("Прямые (переменные) расходы (всего)", "expenses_total"),
        ("  Озон комиссия (за вычетом возвратов)", "commission"),
        ("  Озон фулфилмент:", "fulfil_total"),
        ("    - логистика", "fulfil_logistics"),
        ("    - обратная логистика", "fulfil_reverse"),
        ("    - последняя миля", "fulfil_lastmile"),
        ("    - обработка, сборка", "fulfil_processing"),
        ("  Озон маркетинг:", "market_total"),
        ("    - реклама (PayPerClick)", "ppc"),
        ("    - продвижение, промо", "promo"),
        ("    - звёзды (Stars)", "stars"),
        ("    - бренд-комиссия", "brand"),
        ("    - отзывы", "reviews"),
        ("  Услуги агентов (эквайринг и пр.)", "agents"),
        ("  Услуги FBO", "fbo"),
        ("  Другие услуги", "other"),
        ("  Прочие начисления", "misc"),
        ("", None),
        ("  Себестоимость с учётом возвратов", "cogs"),
        ("", None),
        ("ВАЛОВАЯ ПРИБЫЛЬ", "margin"),
        ("", None),
        ("Операционные расходы (всего)", None),
        ("  - расходы на персонал", None),
        ("  - административные расходы", None),
        ("  - коммерческие расходы", None),
        ("  - прочие операционные расходы", None),
        ("", None),
        ("ОПЕРАЦИОННАЯ ПРИБЫЛЬ (EBITDA)", "margin"),
        ("", None),
        ("Налоги (УСН 15%)", "tax"),
        ("", None),
        ("ЧИСТАЯ ПРИБЫЛЬ", "net"),
        ("Рентабельность (ROI)", "roi"),
        ("Выплата дивидендов", None),
        ("Нераспределённая прибыль", "net"),
        ("Накопленная прибыль", "net"),
    ]


    NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission",
                "fulfil_total", "fulfil_logistics", "fulfil_reverse",
                "fulfil_lastmile", "fulfil_processing", "reviews",
                "ppc", "promo", "stars", "brand", "market_total",
                "agents", "fbo", "other", "misc", "tax"}

    for label, key in lines:
        row = [""] * 19
        row[0] = label
        if key is None:
            rows.append(row)
            continue

        r_num = len(rows) + 1
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"

        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num) - 1] = round(val, 2)

        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(mcol(m1))
            cB = col_letter(mcol(m2))
            row[qcol(q) - 1] = f"=SUM({cA}{r_num}:{cB}{r_num})"

        rows.append(row)

    add_calc_formulas(rows)
    return rows


def apply_format(ws, n_rows):
    """Форматирование листа P&L: заголовок, блоки, итоги, числа, границы."""
    sid = ws.id
    reqs = []

    def grid(rng):
        m = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", rng)
        if not m:
            m2 = re.match(r"([A-Z]+)(\d+)", rng)
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

    def fmt(rng, bg=None, fg=None, bold=False, italic=False,
            size=10, align=None):
        cf = {}
        if bg:
            cf["backgroundColor"] = bg
        tf = {}
        if fg:
            tf["foregroundColor"] = fg
        if bold:
            tf["bold"] = True
        if italic:
            tf["italic"] = True
        if size:
            tf["fontSize"] = size
        if tf:
            cf["textFormat"] = tf
        if align:
            cf["horizontalAlignment"] = align
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": cf},
            "fields": "userEnteredFormat"}})

    # ─── Цвета ─────────────────────────────────────────────
    NAVY   = {"red": 0.10, "green": 0.18, "blue": 0.35}
    WHITE  = {"red": 1,    "green": 1,    "blue": 1}
    BLUE   = {"red": 0.10, "green": 0.45, "blue": 0.91}   # 1A73E8
    GREY_H = {"red": 0.93, "green": 0.93, "blue": 0.93}
    GREY_T = {"red": 0.50, "green": 0.50, "blue": 0.50}
    GREEN_BG = {"red": 0.90, "green": 0.96, "blue": 0.92} # E6F4EA
    GREEN_FG = {"red": 0.07, "green": 0.45, "blue": 0.20} # 137333
    RED_BG   = {"red": 0.99, "green": 0.91, "blue": 0.90} # FCE8E6
    RED_FG   = {"red": 0.77, "green": 0.13, "blue": 0.12} # C5221F
    YEL_BG   = {"red": 1.00, "green": 0.95, "blue": 0.80} # FFF2CC
    YEL_FG   = {"red": 0.50, "green": 0.38, "blue": 0.00} # 7F6000
    NET_POS_BG = {"red": 0.85, "green": 0.92, "blue": 0.83}
    NET_NEG_BG = {"red": 0.96, "green": 0.80, "blue": 0.80}
    NET_POS_FG = {"red": 0.15, "green": 0.31, "blue": 0.07}
    NET_NEG_FG = {"red": 0.60, "green": 0.00, "blue": 0.00}
    BORDER_MED = {"red": 0.75, "green": 0.75, "blue": 0.75}

    # ─── 1. Заголовок A1:S1 ────────────────────────────────
    reqs.append({"unmergeCells": {"range": grid("A1:S1")}})
    reqs.append({"mergeCells": {"range": grid("A1:S1"),
                                "mergeType": "MERGE_ALL"}})
    fmt("A1:S1", bg=BLUE, fg=WHITE, bold=True, size=16, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 45}, "fields": "pixelSize"}})

    # ─── 2. Шапка колонок (строка 2) ───────────────────────
    fmt("A2:S2", bg=GREY_H, fg=NAVY, bold=True, size=11, align="CENTER")
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 32}, "fields": "pixelSize"}})

    # ─── 3. Справочные строки (3-6) ────────────────────────
    for r in (3, 4, 5, 6):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=10)

    # ─── 4. ДОХОДЫ (8) + подстроки (9-12) ──────────────────
    fmt("A8:S8",  bg=GREEN_BG, fg=GREEN_FG, bold=True, size=11)
    for r in (9, 10, 11, 12):
        fmt(f"A{r}:S{r}", size=10)

    # ─── 5. ПРЯМЫЕ РАСХОДЫ (14) + подстроки (15-27) ────────
    fmt("A14:S14", bg=RED_BG, fg=RED_FG, bold=True, size=11)
    SUB_SUB = {17, 18, 19, 20, 22, 23}          # логистика, отзывы и пр.
    for r in range(15, 28):
        if r in SUB_SUB:
            fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=9)
        else:
            fmt(f"A{r}:S{r}", size=10)

    # ─── 6. Себестоимость (29) ─────────────────────────────
    fmt("A29:S29", fg=RED_FG, bold=True, size=10)

    # ─── 7. ВАЛОВАЯ ПРИБЫЛЬ (31) ───────────────────────────
    fmt("A31:S31", bg=YEL_BG, fg=YEL_FG, bold=True, size=11)

    # ─── 8. ОПЕРАЦИОННЫЕ (33-37) ───────────────────────────
    fmt("A33:S33", bg=GREY_H, fg=NAVY, bold=True, size=11)
    for r in range(34, 38):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=9)

    # ─── 9. EBITDA (39) ────────────────────────────────────
    fmt("A39:S39", bg=YEL_BG, fg=YEL_FG, bold=True, size=11)

    # ─── 10. Налоги (41) ───────────────────────────────────
    fmt("A41:S41", fg=RED_FG, bold=True, size=10)

    # ─── 11. ЧИСТАЯ ПРИБЫЛЬ (43) — по знаку B43 ────────────
    net_val = 0.0
    try:
        cell = ws.acell("B43").value
        if cell:
            net_val = float(str(cell).replace(" ", "").replace(",", "."))
    except Exception:
        pass
    if net_val >= 0:
        fmt("A43:S43", bg=NET_POS_BG, fg=NET_POS_FG, bold=True, size=13)
    else:
        fmt("A43:S43", bg=NET_NEG_BG, fg=NET_NEG_FG, bold=True, size=13)

    # ─── 12. ROI и хвост (44-47) ───────────────────────────
    for r in range(44, 48):
        fmt(f"A{r}:S{r}", fg=GREY_T, italic=True, size=10)

    # ─── 13. Выравнивание ──────────────────────────────────
    for r in range(3, n_rows + 1):
        fmt(f"A{r}", align="LEFT")
        fmt(f"B{r}:S{r}", align="RIGHT")

    # ─── 14. Number format ─────────────────────────────────
    RUB = '#,##0.00" ₽";[Red]-#,##0.00" ₽"'
    PCT = '0.00" %"'
    reqs.append({"repeatCell": {
        "range": grid(f"B3:S{n_rows}"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": RUB}}},
        "fields": "userEnteredFormat.numberFormat"}})
    # ROI — проценты
    reqs.append({"repeatCell": {
        "range": grid("B44:S44"),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": PCT}}},
        "fields": "userEnteredFormat.numberFormat"}})

    # ─── 15. Ширины ────────────────────────────────────────
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 340}, "fields": "pixelSize"}})
    reqs.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": 1, "endIndex": 2},
        "properties": {"pixelSize": 130}, "fields": "pixelSize"}})
    for i in range(2, 19):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": 95}, "fields": "pixelSize"}})

    # ─── 16. Заморозка — ТОЛЬКО строки (без колонок) ───────
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount"}})

    # ─── 17. Границы ───────────────────────────────────────
    reqs.append({"updateBorders": {
        "range": grid("A1:S1"),
        "bottom": {"style": "SOLID_THICK", "color": BLUE}}})
    for rng in ("A8:S8", "A14:S14", "A33:S33"):
        reqs.append({"updateBorders": {
            "range": grid(rng),
            "top":    {"style": "SOLID", "color": BORDER_MED},
            "bottom": {"style": "SOLID", "color": BORDER_MED}}})
    for rng in ("A31:S31", "A39:S39", "A43:S43"):
        reqs.append({"updateBorders": {
            "range": grid(rng),
            "top":    {"style": "SOLID_THICK", "color": NAVY},
            "bottom": {"style": "SOLID",       "color": BORDER_MED}}})

    ws.spreadsheet.batch_update({"requests": reqs})


def apply_notes(ws):
    """Примечания (tooltips) к строкам P&L."""
    NOTES = {
        3:  "Количество заказов за период. Справочно, не входит в расчёт P&L.",
        4:  "Баллы за скидки, начисленные Ozon. Справочно.",
        5:  "Сумма соответствует «Всего к начислению» из Отчёта о реализации. В P&L = Продажи − Комиссия Ozon.",
        6:  "Сумма из Акта сверки Ozon. Используется для сверки с банком.",
        8:  "База 100% для расчёта процентов. Остальные строки — в % от этой суммы.",
        9:  "Продажи минус возвраты. Основной доход.",
        10: "Компенсация от Ozon за скидки продавца.",
        11: "Соинвестиции Ozon в продвижение товара.",
        12: "Прочие компенсации от Ozon.",
        14: "Сумма всех переменных расходов: комиссия, фулфилмент, маркетинг, услуги агентов, FBO.",
        15: "Комиссия Ozon за вычетом возвратов. Основная статья расходов.",
        16: "Сумма строк 17–20.",
        17: "Логистика прямых отправлений (FBO/FBS).",
        18: "Возвраты покупателей.",
        19: "Доставка до пункта выдачи.",
        20: "Обработка и сборка заказов на складе Ozon.",
        21: "Сумма строк 22–23.",
        22: "Реклама в Ozon.",
        23: "Услуги по работе с отзывами.",
        24: "Эквайринг и прочие агентские услуги.",
        25: "Хранение и обработка на складе Ozon.",
        26: "Прочие услуги Ozon.",
        27: "Начисления, не попавшие в другие категории.",
        29: "cost_price × количество. Обновляется через файл себестоимости.",
        31: "= Доходы − Прямые расходы − Себестоимость.",
        33: "Постоянные расходы: персонал, админ, коммерческие.",
        34: "Зарплата, налоги с ФОТ.",
        35: "Аренда, связь, канцелярия.",
        36: "Реклама вне Ozon, упаковка.",
        37: "Прочие операционные расходы.",
        39: "= Валовая прибыль − Операционные расходы.",
        41: "База расчёта: уточнить у бухгалтера (от валовой или от выручки).",
        43: "= EBITDA − Налоги. Зелёный фон — плюс, красный — минус.",
        44: "= Чистая прибыль / Себестоимость × 100%.",
        45: "Выплачено за период.",
        46: "= Чистая прибыль − Дивиденды.",
        47: "Сумма по всем месяцам на текущий момент.",
    }
    sid = ws.id
    reqs = []
    for r, text in NOTES.items():
        reqs.append({"updateCells": {
            "range": {"sheetId": sid,
                      "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "rows": [{"values": [{"note": text}]}],
            "fields": "note"}})
    for i in range(0, len(reqs), 50):
        ws.spreadsheet.batch_update({"requests": reqs[i:i+50]})
    print(f"[OK] Примечаний: {len(reqs)}")


def read_operational(ws):
    """Читает ручной ввод ТОЛЬКО из колонок C:N (месяцы) строк 37-40.
    Колонки A (заголовки), B (формула года), O:R (кварталы) НЕ трогает."""
    saved = {}
    for r in (37, 38, 39, 40):
        try:
            row = ws.row_values(r, value_render_option="UNFORMATTED_VALUE")
            # C..N = 1-based колонки 3..14 = 0-based индексы 2..13
            for idx in range(2, 14):
                if idx < len(row):
                    v = row[idx]
                    if v is not None and str(v).strip() not in ("", "0"):
                        saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass
    return saved


def restore_operational(ws, saved):
    """Возвращает ручные значения обратно в 34-37 после sync."""
    if not saved:
        print("[i] Ручных значений не найдено")
        return
    updates = []
    for addr, val in saved.items():
        # Пытаемся преобразовать в число
        try:
            num = float(str(val).replace(" ", "").replace("\xa0", "").replace(",", "."))
            updates.append({"range": addr, "values": [[num]]})
        except (ValueError, AttributeError):
            updates.append({"range": addr, "values": [[val]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"[OK] Восстановлено ручных значений: {len(saved)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(args[0]) if args else 2026
    local = "--local" in sys.argv

    print("=" * 80)
    print(f"ВЫГРУЗКА P&L ЗА {year}  {'(локально)' if local else ''}")
    print("=" * 80)

    rows = build_table(year)
    print(f"\nСтрок: {len(rows)}")

    if local:
        # Сохраняем локально в CSV
        import csv
        out = os.path.join(APP_DIR, f"pnl_{year}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerows(rows)
        print(f"\n[OK] Сохранено: {out}")
        # Печатаем ключевые строки
        print()
        for row in rows:
            a = row[0] if row else ""
            b = row[1] if len(row) > 1 else ""
            print(f"  {a:<50} {b}")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet("P&L")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="P&L", rows=100, cols=25)

    saved_op = read_operational(ws)
    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    restore_operational(ws, saved_op)
    print(f"Записано строк: {len(rows)}")

    apply_format(ws, len(rows))


    print(f"\nГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
