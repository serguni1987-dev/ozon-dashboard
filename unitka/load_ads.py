import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from .ozon_performance_client import OzonPerformanceClient
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

def _f(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    return float(str(v).replace(",", ".").replace(" ", ""))

def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ad_campaigns_daily (
            date TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            campaign_name TEXT,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            expense REAL DEFAULT 0,
            orders INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id)
        )
    """)
    conn.commit()
    conn.close()

def main(days_back=30):
    from .ingestion_safety import integer,atomic,IngestionError
    from .secondary_ingestion import campaign_list,ad_rows
    end=datetime.now().date();start=end-timedelta(days=integer(days_back));client=OzonPerformanceClient();campaigns=campaign_list(client.get('/api/client/campaign'));rows=[]
    for ident,name in campaigns.items():
        response=client.get('/api/client/statistics/daily/json',params={'campaignIds':ident,'dateFrom':start.isoformat(),'dateTo':end.isoformat()});rows.extend(ad_rows(response,ident,start.isoformat(),end.isoformat(),name))
    if not rows:raise IngestionError('Entire ad snapshot empty; review before replacing history')
    init_db();conn=connect()
    try:
        with atomic(conn):
            for ident in campaigns:conn.execute('DELETE FROM ad_campaigns_daily WHERE campaign_id=? AND date BETWEEN ? AND ?',(ident,start.isoformat(),end.isoformat()))
            conn.executemany('INSERT INTO ad_campaigns_daily(date,campaign_id,campaign_name,impressions,clicks,expense,orders,revenue) VALUES (?,?,?,?,?,?,?,?)',rows)
    finally:conn.close()
    return {'status':'OK','rows':len(rows),'campaigns':len(campaigns)}

if __name__ == '__main__':
    main()
