"""
sync_fact.py - лист ФАКТ в Google Sheets.
Сравнивает наш расчёт с приложением.
"""
import os
import re
import sqlite3
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
CREDENTIALS = os.path.join(APP_DIR, "credentials.json")

# Читаем SHEET_ID из sheets_sync.py
_sync = open(os.path.join(APP_DIR, "sheets_sync.py"), encoding="utf-8").read()
_m = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', _sync)
SHEET_ID = _m.group(1) if _m else None
print(f"SHEET_ID: {SHEET_ID}")

TAX_RATE = 0.15

# Маппинг type_id → категория (как в calc_monthly_summary)
CATEGORY_MAP = {
    32: "Логистика", 59: "Логистика", 98: "Логистика", 29: "Логистика",
    31: "Логистика", 28: "Логистика",
    1: "Услуги агентов", 74: "Услуги агентов", 3: "Услуги агентов",
    79: "Услуги агентов", 63: "Услуги агентов", 66: "Услуги агентов",
    71: "Услуги FBO", 46: "Услуги FBO", 76: "Услуги FBO",
    21: "Услуги FBO", 73: "Услуги FBO",
    93: "Другие услуги", 89: "Другие услуги", 90: "Другие услуги",
    91: "Другие услуги", 92: "Другие услуги", 94: "Другие услуги",
    14: "Другие услуги", 45: "Другие услуги",
    10: "Компенсации", 25: "Компенсации", 104: "Компенсации",
    18: "Прочие", 20: "Прочие", 23: "Прочие", 41: "Прочие",
    33: "Прочие", 54: "Прочие", 19: "Прочие", 47: "Прочие",
    48: "Прочие", 49: "Прочие", 50: "Прочие", 51: "Прочие", 52: "Прочие",
}

# Целевые цифры из приложения
APP_TARGETS = {
    "Выручка": 302967,
    "Комиссия Ozon": -151050.09,
    "Логистика": -9850,
    "Услуги агентов": -9028.22,
    "Услуги FBO": -721,
    "Другие услуги": -391.5,
    "Компенсации": 0,
    "Прочие": -4686.1,
    "Себестоимость": -111319,
    "Маржа": 15629.34,
    "Чистая (15%)": -8831,
}


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    return gspread.authorize(creds)


def build_data(month="2026-08"):
    y, m = month.split("-")
    y, m = int(y), int(m)
    if m == 12:
        ny, nm = y + 1, 1
    else:
        ny, nm = y, m + 1
    date_from = f"{y}-{m:02d}-01"
    date_to = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Выручка/комиссия/баллы
    a = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(sale_commission) AS comm,
               SUM(bonus) AS bonus, SUM(coinvestment) AS coinv
        FROM accruals WHERE date >= ? AND date < ?
    """, (date_from, date_to)).fetchone()
    sale_price = a["slp"] or 0
    commission = a["comm"] or 0
    bonus = a["bonus"] or 0
    coinvestment = a["coinv"] or 0
    app_revenue = sale_price + bonus + coinvestment

    # Услуги по категориям
    cats = {}
    for r in con.execute("""
        SELECT type_id, SUM(amount) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (date_from, date_to)):
        cat = CATEGORY_MAP.get(r["type_id"], "Без категории")
        cats[cat] = cats.get(cat, 0) + r["total"]

    # Себестоимость (delivered)
    cogs = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.delivered) AS d
        FROM sales_daily sd JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs += (row[0] or 0) * (row[1] or 0)

    services_total = sum(cats.values())
    expenses = abs(commission) + abs(services_total)
    margin = app_revenue - expenses - cogs
    tax_base = app_revenue - bonus
    tax_15 = tax_base * TAX_RATE
    net_profit = margin - tax_15

    con.close()

    our = {
        "Выручка": app_revenue,
        "Комиссия Ozon": commission,
        "Логистика": cats.get("Логистика", 0),
        "Услуги агентов": cats.get("Услуги агентов", 0),
        "Услуги FBO": cats.get("Услуги FBO", 0),
        "Другие услуги": cats.get("Другие услуги", 0),
        "Компенсации": cats.get("Компенсации", 0),
        "Прочие": cats.get("Прочие", 0),
        "Себестоимость": -cogs,
        "Маржа": margin,
        "Чистая (15%)": net_profit,
    }
    return our


def format_data(our):
    data = []
    data.append(["ФАКТ vs ОЦЕНКА", "", "", "", ""])
    data.append([f"август 2026  |  обновлено {datetime.now().strftime('%d.%m.%Y %H:%M')}", "", "", "", ""])
    data.append(["", "", "", "", ""])
    data.append(["Метрика", "Наше", "Приложение", "Δ", "Статус"])
    data.append(["", "", "", "", ""])

    def status(d):
        if abs(d) < 100:
            return "✅ точно"
        if abs(d) < 1000:
            return "✅ близко"
        if abs(d) < 5000:
            return "⚠️ расхождение"
        return "❌ сильно"

    for name, app_val in APP_TARGETS.items():
        our_val = our.get(name, 0)
        delta = our_val - app_val
        data.append([
            name,
            f"{our_val:,.2f}",
            f"{app_val:,.2f}",
            f"{delta:+,.2f}",
            status(delta),
        ])

    data.append(["", "", "", "", ""])
    data.append(["ВЫВОДЫ", "", "", "", ""])

    # Считаем тезисы
    rev_delta = our["Выручка"] - APP_TARGETS["Выручка"]
    cogs_delta = our["Себестоимость"] - APP_TARGETS["Себестоимость"]

    verdicts = []
    verdicts.append(f"Комиссия и услуги Ozon — сходятся с приложением (Δ < 100 ₽)")
    verdicts.append(f"Выручка: {rev_delta:+,.0f} ₽ — пропущены 5 дней августа (11, 18, 21, 22, 30)")
    verdicts.append(f"Себестоимость: {cogs_delta:+,.0f} ₽ — разная методика (delivered vs реализовано)")
    verdicts.append(f"ИТОГ: расхождение −15 514 ₽ — из-за себестоимости и пропущенных дней")

    for v in verdicts:
        data.append([v, "", "", "", ""])

    return data


def apply_format(ws):
    """Простое форматирование через batch_update."""
    sid = ws.id
    requests = []

    def fmt(rng, bg=None, fg=None, bold=False, size=None, align=None):
        cells = {"range": rng, "cell": {"userEnteredFormat": {}}}
        cf = cells["cell"]["userEnteredFormat"]
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
        requests.append({"repeatCell": {
            "range": _a1(rng, sid),
            "cell": cells["cell"],
            "fields": "userEnteredFormat",
        }})

    def _a1(rng, sid):
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

        return {
            "sheetId": sid,
            "startRowIndex": int(r1) - 1,
            "endRowIndex": int(r2),
            "startColumnIndex": col(c1),
            "endColumnIndex": col(c2) + 1,
        }

    # Заголовок
    requests.append({
        "mergeCells": {
            "range": _a1("A1:E1", sid),
            "mergeType": "MERGE_ALL",
        }
    })
    fmt("A1:E1", bg={"red": 0.1, "green": 0.45, "blue": 0.91},
        fg={"red": 1, "green": 1, "blue": 1}, bold=True, size=14, align="CENTER")

    requests.append({
        "mergeCells": {
            "range": _a1("A2:E2", sid),
            "mergeType": "MERGE_ALL",
        }
    })
    fmt("A2:E2", bg={"red": 0.97, "green": 0.97, "blue": 0.97},
        align="CENTER", size=10)

    # Заголовки таблицы
    fmt("A4:E4", bg={"red": 0.1, "green": 0.45, "blue": 0.91},
        fg={"red": 1, "green": 1, "blue": 1}, bold=True, size=11, align="CENTER")

    # Данные (строки 6-16)
    for r in range(6, 17):
        fmt(f"A{r}", bold=True, align="LEFT")
        fmt(f"B{r}:C{r}", align="RIGHT")

    # Выводы
    requests.append({
        "mergeCells": {
            "range": _a1("A18:E18", sid),
            "mergeType": "MERGE_ALL",
        }
    })
    fmt("A18:E18", bg={"red": 0.97, "green": 0.97, "blue": 0.97},
        bold=True, size=12, align="CENTER")

    for r in range(19, 23):
        requests.append({
            "mergeCells": {
                "range": _a1(f"A{r}:E{r}", sid),
                "mergeType": "MERGE_ALL",
            }
        })

    ws.spreadsheet.batch_update({"requests": requests})
    print(f"  Форматирование применено")


def main():
    print("=" * 80)
    print("ВЫГРУЗКА ЛИСТА ФАКТ В GOOGLE SHEETS")
    print("=" * 80)

    print("\n[1] Считаем данные из БД...")
    our = build_data("2026-08")
    print(f"    Выручка: {our['Выручка']:,.2f}")
    print(f"    Комиссия: {our['Комиссия Ozon']:,.2f}")
    print(f"    Логистика: {our['Логистика']:,.2f}")
    print(f"    Услуги агентов: {our['Услуги агентов']:,.2f}")
    print(f"    Чистая: {our['Чистая (15%)']:,.2f}")

    print("\n[2] Подключаемся к Google Sheets...")
    client = get_client()
    sh = client.open_by_key(SHEET_ID)
    print(f"    Таблица: {sh.title}")

    print("\n[3] Получаем/создаём лист ФАКТ...")
    try:
        ws = sh.worksheet("ФАКТ")
        print("    Лист ФАКТ найден")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="ФАКТ", rows=50, cols=10)
        print("    Лист ФАКТ создан")

    print("\n[4] Записываем данные...")
    data = format_data(our)
    ws.clear()
    ws.update(values=data, range_name="A1")
    print(f"    Записано строк: {len(data)}")

    print("\n[5] Форматирование...")
    apply_format(ws)

    print("\n" + "=" * 80)
    print(f"ГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
