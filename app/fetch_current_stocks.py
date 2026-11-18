"""
fetch_current_stocks.py — тянет актуальные остатки из Ozon API.
Сохраняет в таблицу current_stocks в SQLite.
"""
import os
import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v4/product/info/stocks"
DB = "ozon.db"


def init_table(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS current_stocks (
        offer_id      TEXT PRIMARY KEY,
        sku           INTEGER,
        fbo_present   INTEGER,
        fbo_reserved  INTEGER,
        fbs_present   INTEGER,
        fbs_reserved  INTEGER,
        total_present INTEGER,
        total_reserved INTEGER,
        fetched_at    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cs_sku ON current_stocks(sku);
    """)
    con.commit()


def fetch_page(last_id=""):
    response=requests.post(URL,headers=H,json={'filter':{'visibility':'ALL'},'cursor':last_id,'limit':1000},timeout=60)
    if response.status_code!=200:raise RuntimeError(f'Stock API HTTP {response.status_code}')
    data=response.json()
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):raise RuntimeError('Invalid stock response')
    return data


def main():
    from pathlib import Path
    import sys
    root=str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:sys.path.insert(0,root)
    from unitka import config
    from unitka.stock_ingestion import collect,replace_current
    global H,URL
    config.check_credentials();H={'Client-Id':config.OZON_CLIENT_ID,'Api-Key':config.OZON_API_KEY,'Content-Type':'application/json'};URL=config.OZON_BASE_URL.rstrip('/')+'/v4/product/info/stocks'
    path=Path(config.DB_PATH).resolve()
    if not path.is_file():raise FileNotFoundError('Configured database does not exist')
    rows,_=collect(fetch_page);con=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True)
    try:
        init_table(con)
        return replace_current(con,rows,datetime.now().isoformat(timespec='seconds'))
    finally:con.close()


if __name__ == "__main__":
    main()
