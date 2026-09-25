"""
sync_fact.py - лист ФАКТ: P&L вертикальный (2 колонки: Сумма, % от выручки).
"""
import os
import re
import sqlite3
import sys
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
CREDENTIALS = os.path.join(APP_DIR, "credentials.json")
TAX_RATE = 0.15

_sync = open(os.path.join(APP_DIR, "sheets_sync.py"), encoding="utf-8").read()
SHEET_ID = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', _sync).group(1)

CATEGORY_MAP = {
    32: "Логистика", 59: "Логистика", 98: "Логистика",
    1: "Услуги агентов", 74: "Услуги агентов", 79: "Услуги агентов",
    29: "Услуги агентов", 76: "Услуги агентов", 45: "Услуги агентов",
    3: "Реклама",
    71: "Услуги FBO", 46: "Услуги FBO",
    93: "Другие услуги",
    18: "Прочие", 20: "Прочие",
}


def f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def get_pnl(month):
    y, m = month.split("-")
    y, m = int(y), int(m)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d1 = f"{y}-{m:02d}-01"
    d2 = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    sale_price = f(r["slp"])
    bonus = f(r["bonus"])
    coinv = f(r["coinv"])
    commission = abs(f(r["comm"]))

    r2 = con.execute("""
        SELECT SUM(orders_units) AS orders FROM sales_daily
        WHERE date >= ? AND date < ?
    """, (d1, d2)).fetchone()
    orders = int(r2["orders"] or 0)

    cats = {}
    for row in con.execute("""
        SELECT type_id, SUM(amount) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (d1, d2)):
        cat = CATEGORY_MAP.get(row["type_id"], "Без категории")
        cats[cat] = cats.get(cat, 0) + abs(f(row["total"]))

    cogs = 0.0
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

    con.close()

    return {
        "orders": orders,
        "bonus": bonus,
        "revenue": sale_price + bonus + coinv,
        "sale_price": sale_price,
        "coinv": coinv,
        "commission": commission,
        "logistics": cats.get("Логистика", 0),
        "ads": cats.get("Реклама", 0),
        "agents": cats.get("Услуги агентов", 0),
        "fbo": cats.get("Услуги FBO", 0),
        "other_serv": cats.get("Другие услуги", 0),
        "misc": cats.get("Прочие", 0),
        "comp": cats.get("Компенсации", 0),
        "cogs": cogs,
    }


MONTHS_RU = {
    "01": "Январь", "02": "Февраль", "03": "Март", "04": "Апрель",
    "05": "Май", "06": "Июнь", "07": "Июль", "08": "Август",
    "09": "Сентябрь", "10": "Октябрь", "11": "Ноябрь", "12": "Декабрь",
}


def build_rows(month):
    d = get_pnl(month)
    base = d["revenue"] or 1

    # Прямые = комиссия + услуги (БЕЗ себестоимости)
    direct = (d["commission"] + d["logistics"] + d["ads"] + d["agents"]
              + d["fbo"] + d["other_serv"] + d["misc"] + d["comp"])
    margin = base - direct - d["cogs"]
    opex = 0
    ebitda = margin - opex
    tax = margin * TAX_RATE if margin > 0 else 0
    net = ebitda - tax
    roi = net / base * 100 if base else 0

    y, m = month.split("-")
    month_label = f"{MONTHS_RU.get(m, m)} {y}"

    def pct(v):
        return round(v / base * 100, 1)

    rows = []
    rows.append(["ОТЧЁТ О ПРИБЫЛЯХ И УБЫТКАХ OZON", "", ""])
    rows.append([month_label, "", ""])
    rows.append(["", "", ""])

    # СПРАВОЧНО
    rows.append(["СПРАВОЧНО", "", ""])
    rows.append(["Заказы (справочно)", d["orders"], ""])
    rows.append(["Начислено баллов", round(d["bonus"], 2), ""])
    rows.append(["Всего к начислению (Отчёт о реализации)", round(base, 2), ""])
    rows.append(["Сумма Отчёта о реализации", round(d["sale_price"], 2), ""])
    rows.append(["", "", ""])

    # ДОХОДЫ
    rows.append(["ДОХОДЫ", round(base, 2), 100.0])
    rows.append(["  Выручка за вычетом возвратов", round(d["sale_price"], 2), pct(d["sale_price"])])
    rows.append(["  Баллы за скидки", round(d["bonus"], 2), pct(d["bonus"])])
    rows.append(["  Программы партнёров", round(d["coinv"], 2), pct(d["coinv"])])
    rows.append(["  Компенсации", round(d["comp"], 2), pct(d["comp"])])
    rows.append(["", "", ""])

    # ПРЯМЫЕ РАСХОДЫ
    rows.append(["Прямые (переменные) расходы (всего)", round(-direct, 2), pct(-direct)])
    rows.append(["  Озон комиссия (за вычетом возвратов)", round(-d["commission"], 2), pct(-d["commission"])])
    rows.append(["  Озон фулфилмент:", round(-d["logistics"], 2), pct(-d["logistics"])])
    rows.append(["    - логистика", round(-d["logistics"], 2), pct(-d["logistics"])])
    rows.append(["    - обратная логистика", 0, 0.0])
    rows.append(["    - последняя миля", 0, 0.0])
    rows.append(["    - обработка, сборка", 0, 0.0])
    rows.append(["  Озон маркетинг:", round(-d["ads"], 2), pct(-d["ads"])])
    rows.append(["    - услуги продвижения", round(-d["ads"], 2), pct(-d["ads"])])
    rows.append(["    - отзывы", 0, 0.0])
    rows.append(["  Услуги агентов (эквайринг и пр.)", round(-d["agents"], 2), pct(-d["agents"])])
    rows.append(["  Услуги FBO", round(-d["fbo"], 2), pct(-d["fbo"])])
    rows.append(["  Другие услуги", round(-d["other_serv"], 2), pct(-d["other_serv"])])
    rows.append(["  Прочие начисления", round(-d["misc"], 2), pct(-d["misc"])])
    rows.append(["", "", ""])

    # СЕБЕСТОИМОСТЬ (отдельной строкой после прямых)
    rows.append(["  Себестоимость с учётом возвратов", round(-d["cogs"], 2), pct(-d["cogs"])])
    rows.append(["", "", ""])

    # ВАЛОВАЯ
    rows.append(["ВАЛОВАЯ ПРИБЫЛЬ", round(margin, 2), pct(margin)])
    rows.append(["", "", ""])

    # ОПЕРАЦИОННЫЕ
    rows.append(["Операционные расходы (всего)", 0, 0.0])
    rows.append(["  - расходы на персонал", 0, 0.0])
    rows.append(["  - административные расходы", 0, 0.0])
    rows.append(["  - коммерческие расходы", 0, 0.0])
    rows.append(["  - прочие операционные расходы", 0, 0.0])
    rows.append(["", "", ""])

    # EBITDA
    rows.append(["ОПЕРАЦИОННАЯ ПРИБЫЛЬ (EBITDA)", round(ebitda, 2), pct(ebitda)])
    rows.append(["", "", ""])

    # НАЛОГ
    rows.append(["Налоги (УСН 15%)", round(-tax, 2), pct(-tax)])
    rows.append(["", "", ""])

    # ЧИСТАЯ
    rows.append(["ЧИСТАЯ ПРИБЫЛЬ", round(net, 2), pct(net)])
    rows.append(["Рентабельность (ROI)", f"{roi:.2f}%", ""])
    rows.append(["Выплата дивидендов", 0, 0.0])
    rows.append(["Нераспределённая прибыль", round(net, 2), pct(net)])
    rows.append(["Накопленная прибыль", round(net, 2), pct(net)])

    # Собираем строки-разделы для форматирования
    section_rows = []
    for i, row in enumerate(rows, 1):
        name = row[0]
        if name in ("ДОХОДЫ", "ВАЛОВАЯ ПРИБЫЛЬ", "ОПЕРАЦИОННАЯ ПРИБЫЛЬ (EBITDA)", "ЧИСТАЯ ПРИБЫЛЬ"):
            section_rows.append((i, "GREEN"))
        elif name in ("СПРАВОЧНО", "Операционные расходы (всего)", "Налоги (УСН 15%)"):
            section_rows.append((i, "GREY"))

    return rows, section_rows


def apply_format(ws, n_rows, section_rows):
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

    def fmt(rng, bg=None, fg=None, bold=False, size=10, align=None):
        cf = {}
        if bg:
            cf["backgroundColor"] = bg
        if fg or bold or size:
            cf["textFormat"] = {}
            if fg:
                cf["textFormat"]["foregroundColor"] = fg
            if bold:
                cf["textFormat"]["bold"] = True
            if size:
                cf["textFormat"]["fontSize"] = size
        if align:
            cf["horizontalAlignment"] = align
        reqs.append({"repeatCell": {
            "range": grid(rng),
            "cell": {"userEnteredFormat": cf},
            "fields": "userEnteredFormat"}})

    DARK = {"red": 0.22, "green": 0.22, "blue": 0.22}
    WHITE = {"red": 1, "green": 1, "blue": 1}
    GREEN = {"red": 0.85, "green": 0.95, "blue": 0.85}
    GREY = {"red": 0.96, "green": 0.96, "blue": 0.96}

    # Без merge — просто форматирование ячеек
    fmt("A1:C1", bg=DARK, fg=WHITE, bold=True, size=14, align="CENTER")
    fmt("A2:C2", bg=GREY, bold=True, size=11, align="CENTER")

    # Разделы
    for r, color_name in section_rows:
        bg = GREEN if color_name == "GREEN" else GREY
        fmt(f"A{r}:C{r}", bg=bg, bold=True)

    # Остальные — выравнивание
    section_ids = {r for r, _ in section_rows}
    for r in range(3, n_rows + 1):
        if r in section_ids:
            continue
        fmt(f"A{r}", align="LEFT", size=10)
        fmt(f"B{r}", align="RIGHT", size=10)
        fmt(f"C{r}", align="RIGHT", size=10)

    # Ширина
    for col, w in [("A", 340), ("B", 140), ("C", 100)]:
        idx = ord(col) - ord("A")
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": idx, "endIndex": idx + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    # Заморозка
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
        "fields": "gridProperties.frozenRowCount"}})

    ws.spreadsheet.batch_update({"requests": reqs})


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"

    print("=" * 80)
    print(f"ВЫГРУЗКА P&L ЗА {month} В ЛИСТ ФАКТ")
    print("=" * 80)

    rows, section_rows = build_rows(month)
    print(f"\nСтрок: {len(rows)}")
    print(f"Разделов: {len(section_rows)}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet("ФАКТ")
        print("Лист ФАКТ найден")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="ФАКТ", rows=100, cols=5)
        print("Лист ФАКТ создан")

    ws.clear()
    ws.update(values=rows, range_name="A1")
    print(f"Записано строк: {len(rows)}")

    apply_format(ws, len(rows), section_rows)

    print()
    print(f"ГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
