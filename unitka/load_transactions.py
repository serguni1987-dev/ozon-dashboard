import json
import logging
import sys
from datetime import datetime, timedelta
from .ozon_client import OzonClient
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _parse_accrual(acc):
    op_id = str(acc.get('accrual_id'))
    date = acc.get('date')
    total = acc.get('total_amount', {}).get('amount') if isinstance(acc.get('total_amount'), dict) else acc.get('total_amount')
    try:
        amount = float(total) if total is not None else 0.0
    except (ValueError, TypeError):
        amount = 0.0

    trans_type = 'accrual' if amount >= 0 else 'deduction'
    posting = acc.get('posting') or {}
    posting_number = posting.get('posting_number') if isinstance(posting, dict) else None
    sku = None
    products = posting.get('products') if isinstance(posting, dict) else None
    if products and isinstance(products, list) and len(products) > 0:
        sku = products[0].get('sku')

    category = acc.get('accrued_category')
    return {
        'operation_id': op_id, 'date': date, 'type': trans_type,
        'operation_type': category, 'amount': amount,
        'posting_number': posting_number, 'sku': str(sku) if sku else None,
        'raw_json': json.dumps(acc, ensure_ascii=False)
    }

def load_accruals(client, date_from, date_to):
    print(f"--> Загрузка начислений с {date_from} по {date_to}")
    conn = connect()
    cur = conn.cursor()
    start = datetime.strptime(date_from, '%Y-%m-%d')
    end = datetime.strptime(date_to, '%Y-%m-%d')
    current = start
    total_loaded = 0

    while current <= end:
        ds = current.strftime('%Y-%m-%d')
        last_id = ''
        while True:
            payload = {'date': ds, 'last_id': last_id}
            resp = client._post('/v1/finance/accrual/by-day', payload)
            if not resp:
                break
            accruals = resp.get('accruals') or []
            if not accruals:
                break
            for acc in accruals:
                row = _parse_accrual(acc)
                cur.execute("""
                    INSERT OR REPLACE INTO finance_transactions
                    (operation_id, date, type, operation_type, amount, posting_number, sku, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (row['operation_id'], row['date'], row['type'], row['operation_type'], row['amount'], row['posting_number'], row['sku'], row['raw_json']))
                total_loaded += 1
            last_id = resp.get('last_id', '')
            if not last_id:
                break
        current += timedelta(days=1)

    conn.commit()
    conn.close()
    print(f"--> Начислений загружено: {total_loaded}")
    return total_loaded

def load_payouts(client, date_from, date_to):
    print(f"--> Загрузка выплат и балансов с {date_from} по {date_to}")
    conn = connect()
    cur = conn.cursor()
    
    payload = {
        "date": {
            "from": date_from + 'T00:00:00.000Z',
            "to": date_to + 'T23:59:59.999Z'
        },
        "page": 1,
        "page_size": 1000,
        "with_details": True
    }
    total_periods = 0
    total_payouts = 0
    page = 1

    while True:
        payload['page'] = page
        resp = client._post('/v1/finance/cash-flow-statement/list', payload)
        if not resp:
            print("--> Ошибка запроса к API.")
            break
            
        result = resp.get('result', {})
        page_count = result.get('page_count', 1)
        
        # 1. Сохраняем cash_flows (сводка по периодам)
        cash_flows = result.get('cash_flows', [])
        for cf in cash_flows:
            period = cf.get('period', {})
            pb = period.get('begin', '')[:10] if period.get('begin') else None
            pe = period.get('end', '')[:10] if period.get('end') else None
            if not pb or not pe:
                continue
            
            cur.execute("""
                INSERT OR REPLACE INTO balance_periods
                (period_begin, period_end, orders_amount, returns_amount,
                 commission_amount, services_amount, delivery_amount, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pb, pe, cf.get('orders_amount'), cf.get('returns_amount'),
                  cf.get('commission_amount'), cf.get('services_amount'),
                  cf.get('item_delivery_and_return_amount'),
                  json.dumps(cf, ensure_ascii=False)))
            total_periods += 1
        
        # 2. Сохраняем details (балансы и выплаты)
        details_list = result.get('details', [])
        if not isinstance(details_list, list):
            details_list = [details_list] if isinstance(details_list, dict) else []
            
        for detail in details_list:
            if not isinstance(detail, dict):
                continue
                
            period = detail.get('period', {})
            pb = period.get('begin', '')[:10] if period.get('begin') else None
            pe = period.get('end', '')[:10] if period.get('end') else None
            if not pb or not pe:
                continue
            
            begin_bal = detail.get('begin_balance_amount', 0)
            end_bal = detail.get('end_balance_amount', 0)
            
            payments = detail.get('payments', [])
            total_pay = sum(abs(float(p.get('payment', 0) or 0)) for p in payments if isinstance(p, dict))
            
            cur.execute("""
                INSERT OR REPLACE INTO balance_periods
                (period_begin, period_end, begin_balance, end_balance, payments_total, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pb, pe, begin_bal, end_bal, total_pay, json.dumps(detail, ensure_ascii=False)))
            
            for idx, p in enumerate(payments):
                payment_amount = p.get('payment', 0)
                try:
                    payment_amount = float(payment_amount)
                except (ValueError, TypeError):
                    payment_amount = 0.0
                    
                if payment_amount < 0:
                    amount_to_save = abs(payment_amount)
                    period_id = period.get('id', '0')
                    payout_id = f"{period_id}_{pb}_{idx}"
                    
                    cur.execute("""
                        INSERT OR REPLACE INTO finance_payouts
                        (payout_id, date, amount, period_from, period_to, status, raw_json, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (payout_id, pe, amount_to_save, pb, pe, 'completed', json.dumps(p, ensure_ascii=False)))
                    total_payouts += 1

        if page >= page_count:
            break
        page += 1

    conn.commit()
    conn.close()
    print(f"--> Периодов сохранено: {total_periods}, выплат: {total_payouts}")
    return total_periods
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