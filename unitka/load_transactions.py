import json
import logging
import sys
from datetime import datetime, timedelta
from .ozon_client import OzonClient
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _parse_accrual(acc):
    from .finance_ingestion import parse_accrual
    return parse_accrual(acc)

def _fetch_accrual_day(client, day):
    rows_all = []
    last_id = ""
    seen = set()
    for _ in range(200):
        response = client._post('/v1/finance/accrual/by-day', {'date': day, 'last_id': last_id})
        if not isinstance(response, dict) or not isinstance(response.get('accruals'), list):
            raise RuntimeError(f"Invalid accrual response for {day}")
        rows = response['accruals']
        if any(not isinstance(row, dict) for row in rows):
            raise RuntimeError(f"Invalid accrual rows for {day}")
        next_id = str(response.get('last_id') or '')
        if not rows:
            if next_id:
                raise RuntimeError(f"Empty page with continuation for {day}")
            return rows_all
        rows_all.extend(rows)
        if not next_id:
            return rows_all
        if next_id == last_id or next_id in seen:
            raise RuntimeError(f"Repeated accrual cursor for {day}")
        seen.add(next_id)
        last_id = next_id
    raise RuntimeError(f"Accrual pagination limit exceeded for {day}")


def load_accruals(client,date_from,date_to):
    from .ingestion_safety import span
    from .finance_ingestion import validated_day
    span(date_from,date_to);start=datetime.strptime(date_from,'%Y-%m-%d');end=datetime.strptime(date_to,'%Y-%m-%d');conn=connect()
    try:
        with conn:
            cur=conn.cursor();current=start;total_loaded=0
            while current<=end:
                ds=current.strftime('%Y-%m-%d');rows=validated_day(_fetch_accrual_day(client,ds),ds)
                for row in rows:
                    cur.execute('INSERT OR REPLACE INTO finance_transactions(operation_id,date,type,operation_type,amount,posting_number,sku,raw_json,fetched_at) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',tuple(row[k] for k in ('operation_id','date','type','operation_type','amount','posting_number','sku','raw_json')));total_loaded+=1
                current+=timedelta(days=1)
        return total_loaded
    finally:conn.close()


def load_payouts(client,date_from,date_to):
    from .finance_ingestion import payout_pages,normalize_periods,save_periods
    from .ingestion_safety import span
    span(date_from,date_to);conn=connect()
    try:return save_periods(conn,*normalize_periods(payout_pages(client,date_from,date_to)))
    finally:conn.close()

def main(date_from, date_to):
    print("=== СТАРТ load_transactions ===")
    client = OzonClient()
    load_accruals(client, date_from, date_to)
    load_payouts(client, date_from, date_to)
    print("=== КОНЕЦ load_transactions ===")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Использование: python -m unitka.load_transactions YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
