"""unitka/load_returns.py — загрузка возвратов FBO/FBS из Ozon API."""
import json
import logging
from datetime import datetime, timedelta

from .ozon_client import OzonClient
from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS returns_daily (
            return_id TEXT PRIMARY KEY,
            date TEXT,
            sku TEXT,
            offer_id TEXT,
            posting_number TEXT,
            quantity INTEGER,
            price REAL,
            reason TEXT,
            schema TEXT,
            status TEXT,
            raw_json TEXT,
            fetched_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def parse_return(r):
    """Преобразует один возврат из API в строку для БД."""
    return_id = str(r.get("return_id") or r.get("id") or "")
    logistic = r.get("logistic") or {}
    date = logistic.get("return_date") or r.get("created_at") or ""
    product = r.get("product") or {}
    sku = str(product.get("sku") or "")
    offer_id = product.get("offer_id")
    quantity = product.get("quantity") or 0
    price = product.get("price") or 0
    reason = r.get("return_reason_name") or ""
    schema = r.get("schema") or ""
    visual = r.get("visual") or {}
    status_obj = visual.get("status") or {}
    status = status_obj.get("sys_name") or ""
    posting = r.get("posting_number") or r.get("order_id") or ""

    try:
        price = float(price)
    except (TypeError, ValueError):
        price = 0.0

    return {
        "return_id": return_id,
        "date": date[:10] if date else "",
        "sku": sku or None,
        "offer_id": offer_id,
        "posting_number": posting,
        "quantity": int(quantity) if quantity else 0,
        "price": price,
        "reason": reason,
        "schema": schema,
        "status": status,
        "raw_json": json.dumps(r, ensure_ascii=False),
    }


def load_returns(days_back=30):
    client = OzonClient()
    conn = connect()
    cur = conn.cursor()

    date_to = datetime.now()
    date_from = date_to - timedelta(days=days_back)
    time_from = date_from.strftime("%Y-%m-%dT00:00:00Z")
    time_to = date_to.strftime("%Y-%m-%dT23:59:59Z")

    logger.info("Загрузка возвратов с %s по %s", time_from[:10], time_to[:10])

    total = 0
    last_id = 0
    while True:
        payload = {
            "filter": {
                "logistic_return_date": {
                    "time_from": time_from,
                    "time_to": time_to,
                }
            },
            "limit": 500,
            "last_id": last_id,
        }
        resp = client._post("/v1/returns/list", payload)
        if not resp:
            logger.warning("Нет ответа от API (last_id=%s)", last_id)
            break
        returns = resp.get("returns") or resp.get("result") or []
        if not returns:
            break
        for r in returns:
            row = parse_return(r)
            if not row["return_id"]:
                continue
            cur.execute("""
                INSERT OR REPLACE INTO returns_daily
                (return_id, date, sku, offer_id, posting_number, quantity, price,
                 reason, schema, status, raw_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                row["return_id"], row["date"], row["sku"], row["offer_id"],
                row["posting_number"], row["quantity"], row["price"],
                row["reason"], row["schema"], row["status"], row["raw_json"],
            ))
            total += 1
        last_id = resp.get("last_id") or 0
        logger.info("Чанк: %s возвратов, всего %s", len(returns), total)
        if not last_id:
            break

    conn.commit()
    conn.close()
    logger.info("Всего загружено возвратов: %s", total)


if __name__ == "__main__":
    init_db()
    load_returns(30)
