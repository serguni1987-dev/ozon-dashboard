import logging
from datetime import datetime
from .ozon_client import OzonClient
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Загрузка отзывов из Ozon API...")
    client = OzonClient()
    conn = connect()
    cur = conn.cursor()

    # Очищаем старые данные перед загрузкой
    cur.execute("DELETE FROM sku_reviews")

    # Собираем агрегаты по SKU: {sku: {'sum_rating': 0, 'count': 0, 'bad': 0}}
    reviews_data = {}
    
    last_id = ""
    total_loaded = 0
    
    while True:
        payload = {
            "limit": 100,
            "status": "ALL",
            "last_id": last_id
        }
        resp = client._post('/v1/review/list', payload)
        if not resp:
            break
            
        reviews = resp.get('reviews', [])
        if not reviews:
            break
            
        for r in reviews:
            sku = str(r.get('sku'))
            rating = r.get('rating', 0)
            if not sku or sku == 'None': continue
            
            if sku not in reviews_data:
                reviews_data[sku] = {'sum': 0, 'count': 0, 'bad': 0}
            
            reviews_data[sku]['sum'] += rating
            reviews_data[sku]['count'] += 1
            if rating <= 3:
                reviews_data[sku]['bad'] += 1
                
            total_loaded += 1
            
        last_id = resp.get('last_id', '')
        if not last_id:
            break
            
    # Записываем в БД
    fetched_at = datetime.now().isoformat()
    for sku, data in reviews_data.items():
        avg_rating = round(data['sum'] / data['count'], 2) if data['count'] > 0 else 0
        cur.execute("""
            INSERT OR REPLACE INTO sku_reviews 
            (sku, avg_rating, total_reviews, bad_reviews, fetched_at)
            VALUES (?, ?, ?, ?, ?)
        """, (sku, avg_rating, data['count'], data['bad'], fetched_at))

    conn.commit()
    
    # Итоговый отчет
    cur.execute("SELECT COUNT(*), SUM(total_reviews), SUM(bad_reviews) FROM sku_reviews")
    skus, total_r, total_bad = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM sku_reviews WHERE avg_rating < 4.5 AND total_reviews > 0")
    low_rating = cur.fetchone()[0]
    
    conn.close()
    
    logger.info(f"Загружено отзывов: {total_loaded}")
    logger.info(f"SKU с отзывами: {skus}")
    logger.info(f"Плохих отзывов (1-3 звезды): {total_bad}")
    logger.info(f"SKU с рейтингом ниже 4.5: {low_rating}")

if __name__ == '__main__':
    main()