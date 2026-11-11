"""unitka/calc_change_log.py — лист «Журнал изменений»."""
import os
import logging
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
from .config import SHEET_ID  # ID таблицы: app\.env → PULT_SHEET_ID
SHEET_TITLE = "Журнал изменений"


def load_changes(days_back: int = 30):
    """Загружает последние изменения и проверяет эффект."""
    conn = connect()
    cur = conn.cursor()

    d_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT id, date, sku, field, old_value, new_value, source, comment
        FROM change_log
        WHERE date >= ?
        ORDER BY date DESC
    """, (d_from,))
    rows = cur.fetchall()

    result = []
    for r in rows:
        change_id, date, sku, field, old_value, new_value, source, comment = r

        # Эффект через 7 дней (если изменение было 7+ дней назад)
        effect = ""
        try:
            change_date = datetime.strptime(date.split(" ")[0], "%Y-%m-%d")
            if (datetime.now() - change_date).days >= 7:
                # Продажи до (7 дней до изменения) и после (7 дней после)
                d_before = (change_date - timedelta(days=7)).strftime("%Y-%m-%d")
                d_after = (change_date + timedelta(days=7)).strftime("%Y-%m-%d")

                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) FROM realization_daily
                    WHERE sku = ? AND is_return = 0 AND date >= ? AND date < ?
                """, (sku, d_before, date.split(" ")[0]))
                before = cur.fetchone()[0] or 0

                cur.execute("""
                    SELECT COALESCE(SUM(quantity), 0) FROM realization_daily
                    WHERE sku = ? AND is_return = 0 AND date >= ? AND date < ?
                """, (sku, date.split(" ")[0], d_after))
                after = cur.fetchone()[0] or 0

                if before == 0 and after == 0:
                    effect = "—"
                elif before == 0:
                    effect = f"⬆ +{after} шт (было 0)"
                elif after > before:
                    effect = f"⬆ +{after - before} шт ({int((after / before - 1) * 100)}%)"
                elif after < before:
                    effect = f"⬇ {after - before} шт ({int((after / before - 1) * 100)}%)"
                else:
                    effect = "→ без изменений"
        except Exception:
            effect = "—"

        result.append({
            "date": date,
            "sku": sku,
            "field": field,
            "old": old_value,
            "new": new_value,
            "source": source,
            "comment": comment,
            "effect": effect,
        })

    conn.close()
    return result


def write_to_sheet(changes):
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=500, cols=10)

    values = []
    values.append(["ЖУРНАЛ ИЗМЕНЕНИЙ", "", "", "", "", "", "", ""])
    values.append(["", "", "", "", "", "", "", ""])
    values.append(["Дата", "SKU", "Поле", "Было", "Стало", "Источник", "Комментарий", "Эффект (7 дней)"])
    values.append(["", "", "", "", "", "", "", ""])

    for c in changes:
        values.append([
            c["date"],
            c["sku"],
            c["field"],
            c["old"] or "",
            c["new"] or "",
            c["source"],
            c["comment"],
            c["effect"],
        ])

    if not changes:
        values.append(["Пока нет изменений", "", "", "", "", "", "", ""])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    logger.info("Лист «%s» обновлён (%s записей)", SHEET_TITLE, len(changes))


def main():
    changes = load_changes(days_back=30)
    write_to_sheet(changes)
    logger.info("Журнал изменений: %s записей", len(changes))


if __name__ == "__main__":
    main()
