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
    from .secondary_ingestion import parse_return as parse
    return parse(r)


def load_returns(days_back=30):
    from .ingestion_safety import integer,atomic
    from .secondary_ingestion import fetch_returns
    end=datetime.now().date();start=end-timedelta(days=integer(days_back));rows=fetch_returns(OzonClient(),start.isoformat(),end.isoformat());conn=connect()
    try:
        with atomic(conn):conn.executemany('INSERT OR REPLACE INTO returns_daily(return_id,date,sku,offer_id,posting_number,quantity,price,reason,schema,status,raw_json,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',[tuple(r[k] for k in ('return_id','date','sku','offer_id','posting_number','quantity','price','reason','schema','status','raw_json')) for r in rows])
    finally:conn.close()
    return {'status':'OK','rows':len(rows)}


if __name__ == "__main__":
    init_db()
    load_returns(30)
