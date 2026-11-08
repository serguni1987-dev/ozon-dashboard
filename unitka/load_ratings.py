"""unitka/load_ratings.py — загрузка контент-рейтинга из Ozon Seller API."""
import logging
from datetime import datetime
from .ozon_client import OzonClient
from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sku_content_rating (
            sku TEXT PRIMARY KEY,
            content_rating REAL,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def load_content_ratings():
    client = OzonClient()
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT sku FROM postings_daily WHERE sku IS NOT NULL")
    skus = [str(r[0]) for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT sku FROM stock_daily WHERE sku IS NOT NULL")
    for r in cur.fetchall():
        if str(r[0]) not in skus:
            skus.append(str(r[0]))

    logger.info("Всего SKU для запроса: %s", len(skus))

    total_loaded = 0
    for i in range(0, len(skus), 100):
        chunk = skus[i:i + 100]
        payload = {"skus": chunk}
        try:
            resp = client._post("/v1/product/rating-by-sku", payload)
            if not resp:
                continue
            products = resp.get("products", [])
            for p in products:
                sku = str(p.get("sku"))
                rating = p.get("rating")
                cur.execute("""
                    INSERT OR REPLACE INTO sku_content_rating (sku, content_rating, updated_at)
                    VALUES (?, ?, ?)
                """, (sku, rating, datetime.now().isoformat()))
                total_loaded += 1
            logger.info("Чанк %s: загружено %s рейтингов", i // 100 + 1, len(products))
        except Exception as e:
            logger.error("Ошибка чанка %s: %s", i // 100 + 1, e)

    conn.commit()
    conn.close()
    logger.info("Всего загружено контент-рейтингов: %s", total_loaded)


if __name__ == "__main__":
    init_db()
    load_content_ratings()
