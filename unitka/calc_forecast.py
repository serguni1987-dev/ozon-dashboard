"""unitka/calc_forecast.py — прогноз продаж на следующий месяц по SKU."""
import os
import logging
from datetime import datetime, date
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
SHEET_TITLE = "Прогноз"


def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast (
            sku TEXT PRIMARY KEY,
            forecast_qty REAL DEFAULT 0,
            forecast_revenue REAL DEFAULT 0,
            method TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_seasonal_index(target_month: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT season_index FROM seasonality WHERE month = ?", (target_month,))
    row = cur.fetchone()
    conn.close()
    if row and row[0] is not None:
        return row[0]
    return 1.0


def build():
    today = date.today()
    next_month = (today.month % 12) + 1
    next_year = today.year if today.month < 12 else today.year + 1

    logger.info("Прогноз на %s-%02d", next_year, next_month)

    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT sku,
               AVG(monthly_qty) AS avg_qty,
               AVG(monthly_rev) AS avg_rev
        FROM (
            SELECT sku,
                   substr(date, 1, 7) AS month,
                   SUM(quantity) AS monthly_qty,
                   SUM(sale_price) AS monthly_rev
            FROM realization_daily
            WHERE is_return = 0
              AND date >= date('now', '-3 months')
            GROUP BY sku, month
        )
        GROUP BY sku
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("Нет данных для прогноза")
        return []

    season_index = get_seasonal_index(next_month)

    result = []
    for sku, avg_qty, avg_rev in rows:
        if avg_qty is None:
            continue
        forecast_qty = avg_qty * season_index
        forecast_rev = avg_rev * season_index if avg_rev else 0

        result.append({
            "sku": sku,
            "forecast_qty": round(forecast_qty, 1),
            "forecast_revenue": round(forecast_rev, 2),
            "method": f"avg_3m * season_idx={season_index}",
        })

    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM forecast")
    now = datetime.now().isoformat()
    for r in result:
        cur.execute("""
            INSERT INTO forecast (sku, forecast_qty, forecast_revenue, method, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (r["sku"], r["forecast_qty"], r["forecast_revenue"], r["method"], now))
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
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=6)

    values = []
    values.append(["ПРОГНОЗ ПРОДАЖ", "", "", ""])
    values.append(["", "", "", ""])
    values.append(["SKU", "Прогноз количества", "Прогноз выручки, ₽", "Метод"])
    values.append(["", "", "", ""])
    for r in data:
        values.append([r["sku"], r["forecast_qty"], r["forecast_revenue"], r["method"]])
    values.append(["", "", "", ""])
    total_qty = sum(r["forecast_qty"] for r in data)
    total_rev = sum(r["forecast_revenue"] for r in data)
    values.append(["ИТОГО", total_qty, total_rev, ""])

    ws.clear()  # один запрос
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")  # один запрос
    logger.info("Лист «%s» обновлён", SHEET_TITLE)


def main():
    init_db()
    data = build()
    if data:
        write_to_sheet(data)
        logger.info("Прогноз рассчитан: %s SKU", len(data))
    else:
        logger.warning("Нет данных для прогноза")


if __name__ == "__main__":
    main()
