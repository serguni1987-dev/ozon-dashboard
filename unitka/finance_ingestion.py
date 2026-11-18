"""Strict financial parsing and complete-period payout replacement."""
import hashlib
from .ingestion_safety import IngestionError,number,integer,identifier,day,span,objects,encoded,atomic

def parse_accrual(acc,expected_day=None):
    if not isinstance(acc,dict):raise IngestionError('Invalid accrual')
    ident=str(integer(acc.get('accrual_id'),minimum=1));stamp=day(acc.get('date'))
    if expected_day is not None and stamp!=expected_day:raise IngestionError('Accrual outside requested day')
    amount=number(acc.get('total_amount'));posting=acc.get('posting') or {}
    if not isinstance(posting,dict):raise IngestionError('Invalid posting')
    products=objects(posting.get('products',[]));skus={identifier(p.get('sku')) for p in products}
    return dict(operation_id=ident,date=stamp,type='accrual' if amount>=0 else 'deduction',operation_type=acc.get('accrued_category'),amount=amount,posting_number=acc.get('unit_number') or posting.get('posting_number'),sku=next(iter(skus)) if len(skus)==1 else None,raw_json=encoded(acc))

def validated_day(rows,stamp):
    out=[];seen=set()
    for acc in objects(rows):
        row=parse_accrual(acc,stamp)
        if row['operation_id'] in seen:raise IngestionError('Duplicate daily operation ID')
        seen.add(row['operation_id']);out.append(row)
    return out

def payout_pages(client,start,end):
    span(start,end);out=[];expected=None
    for page in range(1,10001):
        raw=client._post('/v1/finance/cash-flow-statement/list',{'date':{'from':start+'T00:00:00.000Z','to':end+'T23:59:59.999Z'},'page':page,'page_size':1000,'with_details':True})
        if not isinstance(raw,dict) or not isinstance(raw.get('result'),dict):raise RuntimeError('Invalid cash-flow response')
        result=raw['result'];count=result.get('page_count')
        if type(count) is not int or not page<=count<=10000:raise RuntimeError('Invalid page count')
        if expected is None:expected=count
        if count!=expected:raise RuntimeError('Page count changed')
        details=result.get('details')
        if isinstance(details,dict):details=[details]
        flows=objects(result.get('cash_flows'));details=objects(details)
        # Financial periods can straddle the requested window, but cannot be disjoint.
        for row in flows+details:
            period=row.get('period')
            if not isinstance(period,dict):raise IngestionError('Missing cash-flow period')
            a,b=day(period.get('begin')),day(period.get('end'));span(a,b)
            if b<start or a>end:raise IngestionError('Cash-flow period outside requested interval')
        out.append(dict(cash_flows=flows,details=details))
        if page==count:return out
    raise RuntimeError('Cash-flow page limit')

def normalize_periods(pages):
    flows={};details={}
    def key(row):
        p=row.get('period')
        if not isinstance(p,dict):raise IngestionError('Missing cash-flow period')
        a,b=day(p.get('begin')),day(p.get('end'));span(a,b);return a,b
    for page in pages:
        for row in page['cash_flows']:
            k=key(row)
            if k in flows:raise IngestionError('Duplicate cash-flow period')
            values=[number(row.get(f)) for f in ('orders_amount','returns_amount','commission_amount','services_amount','item_delivery_and_return_amount')]
            flows[k]=(*values,encoded(row))
        for row in page['details']:
            k=key(row)
            if k in details:raise IngestionError('Repeated detail period requires review')
            begin=number(row.get('begin_balance_amount'));end=number(row.get('end_balance_amount'));payments=[];seen={}
            for payment in objects(row.get('payments')):
                amount=number(payment.get('payment'));raw=encoded(payment)
                if payment.get('currency_code','RUB')!='RUB':raise IngestionError('Unsupported payout currency')
                if amount>0:raise IngestionError('Positive payment/reversal requires verified semantics')
                if amount<0:
                    token=hashlib.sha256(raw.encode()).hexdigest()[:24];index=seen.get(token,0);seen[token]=index+1
                    payments.append((f'period:{k[0]}:{k[1]}:{token}:{index}',k[1],-amount,k[0],k[1],'completed',raw))
            details[k]=(begin,end,sum(p[2] for p in payments),encoded(row),payments)
    return flows,details

def save_periods(con,flows,details):
    with atomic(con):
        for (a,b),values in flows.items():
            con.execute("""INSERT INTO balance_periods(period_begin,period_end,orders_amount,returns_amount,commission_amount,services_amount,delivery_amount,raw_json) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(period_begin,period_end) DO UPDATE SET orders_amount=excluded.orders_amount,returns_amount=excluded.returns_amount,commission_amount=excluded.commission_amount,services_amount=excluded.services_amount,delivery_amount=excluded.delivery_amount,raw_json=excluded.raw_json""",(a,b,*values))
        for (a,b),(begin,end,total,raw,payments) in details.items():
            con.execute("""INSERT INTO balance_periods(period_begin,period_end,begin_balance,end_balance,payments_total,raw_json) VALUES (?,?,?,?,?,?) ON CONFLICT(period_begin,period_end) DO UPDATE SET begin_balance=excluded.begin_balance,end_balance=excluded.end_balance,payments_total=excluded.payments_total,raw_json=excluded.raw_json""",(a,b,begin,end,total,raw))
            con.execute('DELETE FROM finance_payouts WHERE period_from=? AND period_to=?',(a,b))
            con.executemany('INSERT INTO finance_payouts(payout_id,date,amount,period_from,period_to,status,raw_json,fetched_at) VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',payments)
    return len(flows)
