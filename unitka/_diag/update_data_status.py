"""update_data_status.py — обновляет блок 'СТАТУС ДАННЫХ' в листе НАСТРОЙКИ."""
import sqlite3
import gspread
from google.oauth2.service_account import Credentials
from unitka import config
from datetime import datetime

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def _fmt_date(d):
    """Превращает '2026-11-11' в '11.11.2026' для красоты. Если None — 'Нет данных'."""
    if not d:
        return "Нет данных"
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return str(d)


def _status(d):
    """Проверяет, насколько свежая дата. Возвращает (текст, цвет)."""
    if not d:
        return "❌ Нет данных", "red"
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
        delta = (datetime.now().date() - dt).days
        if delta <= 2:
            return f"✅ Актуально", "green"
        elif delta <= 7:
            return f"⚠️ Отставание {delta} дн.", "yellow"
        else:
            return f"🔴 Устарело на {delta} дн.", "red"
    except Exception:
        return "❓ Ошибка разбора", "yellow"


def main():
    # 1. Смотрим реальные даты в базе
    con = sqlite3.connect(str(config.DB_PATH))
    cur = con.cursor()

    def max_date(table):
        try:
            return cur.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
        except Exception:
            return None

    api_accrual  = max_date("realization_daily")
    api_postings = max_date("postings_daily")
    excel_funnel = max_date("analytics_manual")
    api_tx       = max_date("finance_transactions")
    con.close()

    # 2. Подключаемся к таблице
    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(config.SHEET_ID)
    ws = sh.worksheet("НАСТРОЙКИ")

    # 3. Формируем блок
    today = datetime.now().strftime("%d.%m.%Y")

    rows = [
        ["=== СТАТУС ДАННЫХ ===", "", "", ""],
        ["Источник данных", "Начало периода", "Последняя дата", "Статус"],
        ["API Ozon — начисления", "01.01.2026", _fmt_date(api_accrual),  _status(api_accrual)[0]],
        ["API Ozon — заказы",     "01.01.2026", _fmt_date(api_postings), _status(api_postings)[0]],
        ["Excel Ozon — воронка",  "01.01.2026", _fmt_date(excel_funnel), _status(excel_funnel)[0]],
        ["API Ozon — транзакции", "01.01.2026", _fmt_date(api_tx),       _status(api_tx)[0]],
    ]

    # Записываем в E2:H7
    ws.update(values=rows, range_name="E2:H7")

    # 4. Форматирование
    sid = ws.id
    reqs = []
    # Заголовок блока — серый
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2,
                  "startColumnIndex": 4, "endColumnIndex": 8},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "textFormat": {"bold": True}}},
        "fields": "userEnteredFormat"}})

    # Цвет статуса в колонке H
    colors = {
        "green":  {"red": 0.78, "green": 0.94, "blue": 0.78},
        "yellow": {"red": 1.0,  "green": 0.95, "blue": 0.6},
        "red":    {"red": 1.0,  "green": 0.8,  "blue": 0.8},
    }
    sources = [api_accrual, api_postings, excel_funnel, api_tx]
    for i, d in enumerate(sources):
        color_key = _status(d)[1]
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 2 + i, "endRowIndex": 3 + i,
                      "startColumnIndex": 7, "endColumnIndex": 8},
            "cell": {"userEnteredFormat": {"backgroundColor": colors[color_key]}},
            "fields": "userEnteredFormat.backgroundColor"}})

    sh.batch_update({"requests": reqs})

    # 5. Печать в консоль
    print("=" * 60)
    print(f"СТАТУС ДАННЫХ (обновлён {today})")
    print("=" * 60)
    for r in rows[2:]:
        print(f"  {r[0]:25} | {r[2]:12} | {r[3]}")
    print("=" * 60)


if __name__ == "__main__":
    main()