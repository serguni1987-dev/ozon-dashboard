"""unitka/calc_seasonality.py — анализ сезонности продаж по месяцам."""
import os
import logging
from datetime import datetime
from collections import defaultdict

from .db import connect
from . import report_layout as rl
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "Сезонность"

MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн",
             "июл", "авг", "сен", "окт", "ноя", "дек"]


def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seasonality (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            total_quantity INTEGER DEFAULT 0,
            total_revenue REAL DEFAULT 0,
            season_index REAL DEFAULT 0,
            PRIMARY KEY (year, month)
        )
    """)
    conn.commit()
    conn.close()


def build():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT substr(date, 1, 4) AS year,
               substr(date, 6, 2) AS month,
               SUM(quantity) AS qty,
               SUM(sale_price) AS revenue
        FROM realization_daily
        WHERE is_return = 0
        GROUP BY year, month
        ORDER BY year, month
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("Нет данных для анализа сезонности")
        return []

    total_qty_all = sum(r[2] for r in rows)
    total_months = len(rows)
    avg_qty_per_month = total_qty_all / total_months if total_months else 0

    result = []
    for year, month, qty, revenue in rows:
        month = int(month)
        idx = round(qty / avg_qty_per_month, 2) if avg_qty_per_month else 0
        result.append({
            "year": int(year),
            "month": month,
            "month_name": MONTHS_RU[month - 1],
            "quantity": qty,
            "revenue": revenue,
            "season_index": idx,
        })

    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM seasonality")
    for r in result:
        cur.execute("""
            INSERT INTO seasonality (year, month, total_quantity, total_revenue, season_index)
            VALUES (?, ?, ?, ?, ?)
        """, (r["year"], r["month"], r["quantity"], r["revenue"], r["season_index"]))
    conn.commit()
    conn.close()

    return result


def write_to_sheet(data):
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=50, cols=6)

    # Собираем все значения в один список
    values = []
    values.append(["СЕЗОННОСТЬ ПРОДАЖ", "", "", "", ""])
    values.append(["", "", "", "", ""])
    values.append(["Год", "Месяц", "Количество", "Выручка", "Сезонный индекс"])
    values.append(["", "", "", "", ""])
    for r in data:
        values.append([r["year"], r["month_name"], r["quantity"], r["revenue"], r["season_index"]])
    values.append(["", "", "", "", ""])
    total_qty = sum(r["quantity"] for r in data)
    total_rev = sum(r["revenue"] for r in data)
    values.append(["ИТОГО", "", total_qty, total_rev, ""])

    ws.clear()  # один запрос
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")  # один запрос
    logger.info("Лист «%s» обновлён", SHEET_TITLE)


def main():
    init_db()
    data = build()
    if data:
        write_to_sheet(data)
        logger.info("Сезонность рассчитана: %s месяцев", len(data))
    else:
        logger.warning("Нет данных для сезонности")


if __name__ == "__main__":
    main()
