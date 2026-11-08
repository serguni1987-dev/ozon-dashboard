import json
import logging
from datetime import datetime
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sku_map (
            ozon_sku        TEXT PRIMARY KEY,
            offer_id        TEXT,
            stock_sku       TEXT,
            source          TEXT,
            match_confidence TEXT,
            updated_at      TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sku_map_offer ON sku_map(offer_id)")
    conn.commit()
    conn.close()

def build_map():
    conn = connect()
    cur = conn.cursor()

    # 1. Загружаем SKU из stock_daily
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if not last_date:
        logger.error("Нет данных в stock_daily. Запустите load_stocks.py")
        conn.close()
        return

    cur.execute("SELECT sku FROM stock_daily WHERE date = ?", (last_date,))
    stock_skus = {str(row[0]) for row in cur.fetchall()}
    logger.info(f"Загружено {len(stock_skus)} SKU из stock_daily на {last_date}")

    # 2. Берем уникальные SKU и raw_json из postings_daily
    cur.execute("SELECT DISTINCT sku, raw_json FROM postings_daily WHERE sku IS NOT NULL AND raw_json IS NOT NULL")
    postings_data = cur.fetchall()
    logger.info(f"Найдено {len(postings_data)} уникальных SKU в postings_daily")

    # 3. Сопоставляем
    matched = 0
    with_offer = 0
    for sku_val, raw in postings_data:
        ozon_sku = str(sku_val)
        offer_id = None
        
        # Извлекаем offer_id из raw_json
        try:
            data = json.loads(raw)
            products = data.get('products', [])
            if products:
                offer_id = products[0].get('offer_id')
                if offer_id:
                    with_offer += 1
        except Exception:
            pass

        stock_sku = ozon_sku if ozon_sku in stock_skus else None
        confidence = 'exact' if stock_sku else 'none'
        if stock_sku:
            matched += 1

        cur.execute("""
            INSERT OR REPLACE INTO sku_map 
            (ozon_sku, offer_id, stock_sku, source, match_confidence, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ozon_sku, offer_id, stock_sku, 'postings_raw', confidence, datetime.now().isoformat()))

    conn.commit()

    # 4. Итоговый отчет
    cur.execute("SELECT COUNT(*) FROM sku_map")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sku_map WHERE match_confidence = 'exact'")
    exact = cur.fetchone()[0]

    conn.close()
    logger.info(f"Всего записей в sku_map: {total}")
    logger.info(f"Сопоставлено с остатками (exact): {exact} из {len(postings_data)}")
    logger.info(f"С извлеченным offer_id (артикулом): {with_offer}")

def main():
    init_db()
    build_map()

if __name__ == '__main__':
    main()