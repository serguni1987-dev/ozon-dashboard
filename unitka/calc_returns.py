"""unitka/calc_returns.py — анализ возвратов (источник: postings_daily)."""
import os
import logging
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "Возвраты"


def build():
    conn = connect()
    cur = conn.cursor()

    # Загружаем offer_id
    offer_map = {}
    try:
        cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
        for r in cur.fetchall():
            offer_map[str(r[0])] = r[1]
    except Exception as e:
        logger.error(f"Ошибка чтения sku_map: {e}")

    # 1. Продажи (выкупы) из postings_daily
    cur.execute("""
        SELECT CAST(sku AS INTEGER) AS sku, SUM(quantity) AS qty
        FROM postings_daily
        WHERE status = 'delivered' AND is_returned = 0
        GROUP BY CAST(sku AS INTEGER)
    """)
    sales_by_sku = {str(r[0]): r[1] or 0 for r in cur.fetchall()}

    # 2. Возвраты из postings_daily
    cur.execute("""
        SELECT CAST(sku AS INTEGER) AS sku, SUM(quantity) AS qty, SUM(price * quantity) AS lost_rev
        FROM postings_daily
        WHERE is_returned = 1
        GROUP BY CAST(sku AS INTEGER)
    """)
    returns_by_sku = {str(r[0]): {"qty": r[1] or 0, "lost_rev": r[2] or 0} for r in cur.fetchall()}

    conn.close()

    all_skus = set(sales_by_sku.keys()) | set(returns_by_sku.keys())
    result = []
    
    for sku in all_skus:
        sold = sales_by_sku.get(sku, 0)
        ret_data = returns_by_sku.get(sku, {"qty": 0, "lost_rev": 0})
        returned = ret_data["qty"]
        lost_revenue = abs(ret_data["lost_rev"])

        total = sold + returned
        return_pct = (returned / total * 100) if total > 0 else 0
        lost_logistics = returned * 300  # Оценка логистики возврата
        total_loss = lost_revenue + lost_logistics

        if returned == 0:
            status = "✅ без возвратов"
        elif return_pct > 20:
            status = "🔴 критично"
        elif return_pct > 10:
            status = "🟡 высоко"
        elif return_pct > 5:
            status = "🟢 норма"
        else:
            status = "✅ отлично"

        result.append({
            "sku": sku,
            "offer_id": offer_map.get(sku, ""),
            "sold": sold,
            "returned": returned,
            "return_pct": round(return_pct, 1),
            "lost_revenue": round(lost_revenue, 2),
            "lost_logistics": round(lost_logistics, 2),
            "total_loss": round(total_loss, 2),
            "status": status,
        })

    result.sort(key=lambda x: x["total_loss"], reverse=True)
    return result


def write_to_sheet(data):
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=9)

    total_sold = sum(r["sold"] for r in data)
    total_returned = sum(r["returned"] for r in data)
    total_loss = sum(r["total_loss"] for r in data)
    overall_pct = (total_returned / (total_sold + total_returned) * 100) if (total_sold + total_returned) > 0 else 0

    values = []
    values.append(["АНАЛИЗ ВОЗВРАТОВ", "", "", "", "", "", "", "", ""])
    values.append(["", "", "", "", "", "", "", "", ""])
    values.append([f"Всего продано: {total_sold} шт", "", "", "", "", "", "", "", ""])
    values.append([f"Всего возвращено: {total_returned} шт ({overall_pct:.1f}%)", "", "", "", "", "", "", "", ""])
    values.append([f"Общие потери: {total_loss:,.0f} ₽", "", "", "", "", "", "", "", ""])
    values.append(["", "", "", "", "", "", "", "", ""])
    values.append(["SKU", "Артикул", "Продано", "Возвращено", "% возврата", "Потеря выручки, ₽", "Потеря логистики, ₽", "Общая потеря, ₽", "Статус"])
    values.append(["", "", "", "", "", "", "", "", ""])

    for r in data[:50]:
        values.append([
            r["sku"], r["offer_id"], r["sold"], r["returned"], f"{r['return_pct']}%",
            r["lost_revenue"], r["lost_logistics"], r["total_loss"], r["status"],
        ])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    logger.info("Лист «%s» обновлён (%s SKU)", SHEET_TITLE, len(data))


def main():
    data = build()
    if data:
        write_to_sheet(data)
        critical = sum(1 for r in data if "критично" in r["status"])
        high = sum(1 for r in data if "высоко" in r["status"])
        logger.info("Возвраты: %s SKU (критично: %s, высоко: %s)", len(data), critical, high)
    else:
        logger.warning("Нет данных")


if __name__ == "__main__":
    main()