import logging
from datetime import datetime
from .ozon_client import OzonClient
from .log_change import log_change
from .db import connect

logger = logging.getLogger(__name__)

def load_stocks():
    client = OzonClient()
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_daily (
            date TEXT NOT NULL,
            sku TEXT NOT NULL,
            fbo_present INTEGER DEFAULT 0,
            fbo_reserved INTEGER DEFAULT 0,
            fbs_present INTEGER DEFAULT 0,
            fbs_reserved INTEGER DEFAULT 0,
            PRIMARY KEY (date, sku)
        )
    """)
    
    today = datetime.now().strftime('%Y-%m-%d')
    last_id = ""
    total_items = 0
    
    while True:
        payload = {"filter": {"visibility": "ALL"}, "last_id": last_id, "limit": 1000}
        resp = client._post('/v4/product/info/stocks', payload)
        if not resp:
            break
            
        items = resp.get('items', [])
        if not items:
            break
            
        stocks_agg = {}
        for item in items:
            for stock in item.get('stocks', []):
                sku = str(stock.get('sku'))
                if not sku or sku == 'None':
                    continue
                if sku not in stocks_agg:
                    stocks_agg[sku] = [0, 0, 0, 0]
                if stock.get('type') == 'fbo':
                    stocks_agg[sku][0] += stock.get('present', 0)
                    stocks_agg[sku][1] += stock.get('reserved', 0)
                elif stock.get('type') == 'fbs':
                    stocks_agg[sku][2] += stock.get('present', 0)
                    stocks_agg[sku][3] += stock.get('reserved', 0)
        
        for sku, agg in stocks_agg.items():
            # Получаем предыдущий остаток для логирования
            cur.execute("SELECT fbo_present + fbs_present FROM stock_daily WHERE sku = ? AND date < ? ORDER BY date DESC LIMIT 1", (sku, today))
            prev = cur.fetchone()
            prev_qty = prev[0] if prev else 0
            new_qty = agg[0] + agg[2]
            
            # Логируем изменение, если остаток существенно изменился (>10 шт)
            if abs(new_qty - prev_qty) > 10:
                log_change(sku, "stock", prev_qty, new_qty, source="auto", comment="Изменение остатка")
            
            cur.execute("""
                INSERT OR REPLACE INTO stock_daily
                (date, sku, fbo_present, fbo_reserved, fbs_present, fbs_reserved)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (today, sku, agg[0], agg[1], agg[2], agg[3]))
            total_items += 1
            
        last_id = resp.get('last_id', '')
        if not last_id:
            break
            
    conn.commit()
    conn.close()
    print(f"--> Загружено остатков по {total_items} SKU на {today}")

if __name__ == '__main__':
    load_stocks()