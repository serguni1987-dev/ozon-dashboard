"""Return and advertising payload contracts."""
from .ingestion_safety import IngestionError,number,integer,identifier,day,span,objects,encoded,cursor_pages

def return_page(client,cursor,start,end):
    raw=client._post('/v1/returns/list',{'filter':{'logistic_return_date':{'time_from':start+'T00:00:00Z','time_to':end+'T23:59:59Z'}},'limit':500,'last_id':cursor or 0})
    if not isinstance(raw,dict):raise IngestionError('Invalid return response')
    if 'returns' in raw:rows=raw['returns']
    elif isinstance(raw.get('result'),list):rows=raw['result']
    else:raise IngestionError('Missing returns array')
    cursor=raw.get('last_id',0)
    if isinstance(cursor,bool):raise IngestionError('Invalid returns cursor')
    if cursor in (None,0,'0',''):cursor=''
    return dict(returns=objects(rows),last_id=cursor,has_next=raw.get('has_next'))

def parse_return(r):
    if not isinstance(r,dict):raise IngestionError('Invalid return')
    rid=identifier(r.get('return_id') if r.get('return_id') is not None else r.get('id'));logistic=r.get('logistic') or {};product=r.get('product') or {}
    if not isinstance(logistic,dict) or not isinstance(product,dict):raise IngestionError('Invalid return section')
    visual=r.get('visual') or {};status=(visual.get('status') or {}).get('sys_name') or ''
    return dict(return_id=rid,date=day(logistic.get('return_date') or r.get('created_at')),sku=identifier(product.get('sku')),offer_id=product.get('offer_id'),posting_number=r.get('posting_number') or r.get('order_id') or '',quantity=integer(product.get('quantity'),minimum=1),price=number(product.get('price'),missing=True),reason=r.get('return_reason_name') or '',schema=r.get('schema') or '',status=status,raw_json=encoded(r))

def fetch_returns(client,start,end):
    span(start,end);raw=cursor_pages(lambda c:return_page(client,c,start,end),'returns',page_size=500);out=[];seen=set()
    for item in raw:
        row=parse_return(item)
        if row['return_id'] in seen or not start<=row['date']<=end:raise IngestionError('Duplicate return or wrong period')
        seen.add(row['return_id']);out.append(row)
    return out

def campaign_list(raw):
    if isinstance(raw,dict):
        if raw.get('has_next') or raw.get('last_id') or raw.get('cursor'):raise IngestionError('Incomplete campaign catalogue')
        rows=objects(raw.get('list'));total=raw.get('total',raw.get('total_count'))
        if total is not None and integer(total)!=len(rows):raise IngestionError('Campaign count mismatch')
    else:rows=objects(raw)
    out={}
    for row in rows:
        key=identifier(row.get('id'))
        if key in out:raise IngestionError('Duplicate campaign')
        out[key]=row.get('title') or ''
    if not out:raise IngestionError('Empty campaign catalogue requires review')
    return out

def ad_rows(raw,campaign,start,end,name):
    if isinstance(raw,dict):
        if raw.get('has_next') or raw.get('last_id') or raw.get('cursor'):raise IngestionError('Incomplete ad statistics')
        if 'rows' in raw:items=objects(raw['rows'])
        elif 'campaigns' in raw:
            items=[]
            for group in objects(raw['campaigns']):
                if identifier(group.get('id'))!=campaign:raise IngestionError('Wrong statistics campaign')
                items.extend(objects(group.get('dailyStatistics')))
        else:raise IngestionError('Unknown ad statistics structure')
    else:items=objects(raw)
    out=[];seen=set()
    def pick(item,a,b=None):
        if item.get(a) is not None:return item[a]
        if b is not None and item.get(b) is not None:return item[b]
        raise IngestionError('Required advertising metric missing: '+a)
    for item in items:
        ident=identifier(item.get('campaignId',item.get('campaign_id',campaign)));stamp=day(item.get('date') or item.get('day'))
        if ident!=campaign or not start<=stamp<=end or stamp in seen:raise IngestionError('Unexpected/duplicate statistics row')
        seen.add(stamp);out.append((stamp,campaign,name,integer(pick(item,'impressions')),integer(pick(item,'clicks')),number(pick(item,'expense','moneySpent')),integer(pick(item,'orders','orderedUnits')),number(pick(item,'revenue','orderedRevenue'))))
    return out
