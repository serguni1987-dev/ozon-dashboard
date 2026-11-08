"""unitka/calc_recommendations.py — рекомендации по закупкам на основе прогноза и остатков."""
import os
import logging
from datetime import datetime

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
SHEET_TITLE = "Закупки"


def build():
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if not last_date:
        logger.warning("Нет данных об остатках")
        conn.close()
        return []

    # SKU, которые продавались за последние 60 дней (есть спрос)
    cur.execute("""
        SELECT DISTINCT sku FROM realization_daily
        WHERE is_return = 0 AND date >= date('now', '-60 days')
    """)
    recent_skus = {str(r[0]) for r in cur.fetchall()}

    cur.execute("""
        SELECT f.sku,
               f.forecast_qty,
               f.forecast_revenue,
               COALESCE(s.fbo_present + s.fbs_present, 0) AS stock,
               CASE WHEN s.sku IS NULL THEN 1 ELSE 0 END AS no_stock_data
        FROM forecast f
        LEFT JOIN stock_daily s ON f.sku = s.sku AND s.date = ?
        ORDER BY f.forecast_qty DESC
    """, (last_date,))

    rows = cur.fetchall()
    conn.close()

    if not rows:
        logger.warning("Нет данных для рекомендаций")
        return []

    result = []
    for sku, forecast_qty, forecast_rev, stock, no_stock_data in rows:
        if forecast_qty is None:
            continue

        sku_str = str(sku)
        has_demand = sku_str in recent_skus

        if not has_demand:
            action = "⚪ НЕ ТРОГАТЬ"
            reason = f"нет продаж 60+ дней (прогноз {forecast_qty:.0f})"
            buy_qty = 0
        elif no_stock_data:
            action = "⚠️ НЕТ ДАННЫХ"
            reason = f"SKU отсутствует в остатках Ozon (прогноз {forecast_qty:.0f})"
            buy_qty = 0
        elif stock == 0 and forecast_qty > 0:
            action = "🔴 СРОЧНО ЗАКУПИТЬ"
            reason = f"остаток 0, прогноз {forecast_qty:.0f} шт"
            buy_qty = forecast_qty
        elif stock < forecast_qty:
            action = "🟡 ЗАКУПИТЬ"
            reason = f"остаток {stock} < прогноз {forecast_qty:.0f}"
            buy_qty = forecast_qty - stock
        elif stock > forecast_qty * 3:
            action = "🟢 РАСПРОДАТЬ"
            reason = f"остаток {stock} > прогноз {forecast_qty:.0f} × 3"
            buy_qty = 0
        else:
            action = "✅ НОРМА"
            reason = f"остаток {stock} соответствует прогнозу {forecast_qty:.0f}"
            buy_qty = 0

        result.append({
            "sku": sku,
            "forecast_qty": round(forecast_qty, 1),
            "stock": stock,
            "buy_qty": round(buy_qty, 1),
            "action": action,
            "reason": reason,
            "forecast_revenue": forecast_rev or 0,
        })

    return result


def write_to_sheet(data):
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=7)

    values = []
    values.append(["РЕКОМЕНДАЦИИ ПО ЗАКУПКАМ", "", "", "", "", "", ""])
    values.append(["", "", "", "", "", "", ""])
    values.append(["SKU", "Прогноз", "Остаток", "Закупить", "Действие", "Причина", "Прогноз выручки, ₽"])
    values.append(["", "", "", "", "", "", ""])

    # Сортируем: сначала «СРОЧНО ЗАКУПИТЬ», потом «ЗАКУПИТЬ», потом «РАСПРОДАТЬ», потом «НОРМА»
    priority = {"🔴 СРОЧНО ЗАКУПИТЬ": 0, "🟡 ЗАКУПИТЬ": 1, "🟢 РАСПРОДАТЬ": 2, "⚠️ НЕТ ДАННЫХ": 3, "⚪ НЕ ТРОГАТЬ": 4, "✅ НОРМА": 5}
    sorted_data = sorted(data, key=lambda x: priority.get(x["action"], 4))

    for r in sorted_data:
        values.append([
            r["sku"],
            r["forecast_qty"],
            r["stock"],
            r["buy_qty"],
            r["action"],
            r["reason"],
            r["forecast_revenue"],
        ])

    values.append(["", "", "", "", "", "", ""])
    total_buy = sum(r["buy_qty"] for r in data)
    total_rev = sum(r["forecast_revenue"] for r in data)
    values.append(["ИТОГО", "", "", total_buy, "", "", total_rev])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    logger.info("Лист «%s» обновлён", SHEET_TITLE)


def main():
    data = build()
    if data:
        write_to_sheet(data)
        critical = sum(1 for r in data if "СРОЧНО" in r["action"])
        buy = sum(1 for r in data if "ЗАКУПИТЬ" in r["action"] and "СРОЧНО" not in r["action"])
        sell = sum(1 for r in data if "РАСПРОДАТЬ" in r["action"])
        no_demand = sum(1 for r in data if "НЕ ТРОГАТЬ" in r["action"])
        no_data = sum(1 for r in data if "НЕТ ДАННЫХ" in r["action"])
        logger.info("Рекомендаций: %s (срочно: %s, закупить: %s, распродать: %s, нет спроса: %s, нет данных: %s)",
                    len(data), critical, buy, sell, no_demand, no_data)
    else:
        logger.warning("Нет данных для рекомендаций")


if __name__ == "__main__":
    main()
