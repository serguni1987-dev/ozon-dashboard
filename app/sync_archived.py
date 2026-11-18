"""
sync_archived.py — синхронизация архива с Ozon.
/v3/product/list с visibility ALL не возвращает архивные,
поэтому запрашиваем отдельно ARCHIVED и ALL.
"""
import os
import requests
import sqlite3
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v3/product/list"
DB = "ozon.db"


def fetch_all(visibility):
    from pathlib import Path
    import sys
    root=str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:sys.path.insert(0,root)
    from unitka.ingestion_safety import cursor_pages,IngestionError
    def fetch(cursor):
        response=requests.post(URL,headers=H,json={'filter':{'visibility':visibility},'last_id':cursor,'limit':1000},timeout=60)
        if response.status_code!=200:raise RuntimeError(f'Archive API HTTP {response.status_code}')
        data=response.json()
        if not isinstance(data,dict) or not isinstance(data.get('result'),dict):raise IngestionError('Invalid archive response')
        return data['result']
    return cursor_pages(fetch,'items',page_size=1000)


def main():
    from pathlib import Path
    import sys
    root=str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:sys.path.insert(0,root)
    from unitka import config
    from unitka.ingestion_safety import identifier,atomic,IngestionError
    global H,URL
    config.check_credentials();H={'Client-Id':config.OZON_CLIENT_ID,'Api-Key':config.OZON_API_KEY,'Content-Type':'application/json'};URL=config.OZON_BASE_URL.rstrip('/')+'/v3/product/list'
    all_items=fetch_all('ALL');arch_items=fetch_all('ARCHIVED');by_offer={}
    for items,archive in ((all_items,False),(arch_items,True)):
        seen=set()
        for item in items:
            offer=identifier(item.get('offer_id'))
            if offer in seen:raise IngestionError('Duplicate catalogue offer')
            seen.add(offer);flag=item.get('archived',False)
            if type(flag) is not bool:raise IngestionError('Invalid archived flag')
            by_offer[offer]=int(archive or flag)
    if not by_offer:raise IngestionError('Empty catalogue; archive flags preserved')
    path=Path(config.DB_PATH).resolve()
    if not path.is_file():raise FileNotFoundError('Configured database does not exist')
    con=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True)
    try:
        with atomic(con):con.executemany('UPDATE products SET is_archived=? WHERE offer_id=?',[(flag,offer) for offer,flag in by_offer.items()])
    finally:con.close()
    return {'status':'OK','offers_received':len(by_offer),'unreturned_flags':'preserved, not assumed active'}


if __name__ == "__main__":
    main()
