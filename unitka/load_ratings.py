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
    from .ingestion_safety import objects,identifier,number,atomic,IngestionError
    client=OzonClient();conn=connect()
    try:
        skus=sorted({identifier(r[0]) for r in conn.execute('SELECT sku FROM postings_daily WHERE sku IS NOT NULL UNION SELECT sku FROM stock_daily WHERE sku IS NOT NULL')});rows=[];seen=set();stamp=datetime.now().isoformat()
        for offset in range(0,len(skus),100):
            chunk=skus[offset:offset+100];response=client._post('/v1/product/rating-by-sku',{'skus':chunk})
            if not isinstance(response,dict) or 'products' not in response:raise IngestionError('Invalid rating response')
            received=set()
            for product in objects(response['products']):
                sku=identifier(product.get('sku'));rating=number(product.get('rating'))
                if sku not in chunk or sku in seen or rating<0:raise IngestionError('Unexpected/duplicate rating')
                seen.add(sku);received.add(sku);rows.append((sku,rating,stamp))
            if received!=set(chunk):raise IngestionError('Incomplete rating chunk; previous data preserved')
        with atomic(conn):conn.executemany('INSERT OR REPLACE INTO sku_content_rating(sku,content_rating,updated_at) VALUES (?,?,?)',rows)
        return {'status':'OK' if skus else 'SKIPPED','rows':len(rows)}
    finally:conn.close()


if __name__ == "__main__":
    init_db()
    load_content_ratings()
