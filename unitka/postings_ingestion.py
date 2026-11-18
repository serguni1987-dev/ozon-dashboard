"""Both commission encodings and source-scoped atomic postings writes."""
from .ingestion_safety import IngestionError,number,integer,identifier,day,span,objects,encoded,atomic

def commission_value(record):
    values=[number(record[k]) for k in ('commission_amount','commission') if record.get(k) is not None]
    if len(values)==2 and abs(values[0]-values[1])>.005:raise IngestionError('Conflicting commission formats')
    return values[0] if values else None

def fetch(client,start,end,*,scheme,limit,max_pages=10000):
    span(start,end)
    if scheme not in ('fbs','fbo') or type(limit) is not int or limit<1:raise IngestionError('Invalid postings mode')
    rows=[];seen=set()
    for page in range(max_pages):
        request={'dir':'ASC','filter':{'since':start+'T00:00:00.000Z','to':end+'T23:59:59.999Z'},'limit':limit,'offset':page*limit,'with':{'analytics_data':True,'financial_data':True}}
        raw=client._post('/v4/posting/fbs/list' if scheme=='fbs' else '/v2/posting/fbo/list',request)
        if not isinstance(raw,dict):raise IngestionError('Invalid postings response')
        if scheme=='fbs':
            body=raw.get('result',raw)
            if not isinstance(body,dict) or 'postings' not in body or type(body.get('has_next')) is not bool:raise IngestionError('Missing postings or has_next')
            batch=objects(body['postings']);more=body['has_next']
        else:
            if 'result' not in raw:raise IngestionError('Missing FBO result')
            batch=objects(raw['result']);more=len(batch)==limit
        if len(batch)>limit or (more and not batch):raise IngestionError('Contradictory postings page')
        for row in batch:
            key=identifier(row.get('posting_number'))
            if key in seen:raise IngestionError('Repeated posting across pages')
            seen.add(key)
        rows.extend(batch)
        if not more:return rows
    raise IngestionError('Postings pagination limit')

def normalize(postings,start,end,*,scheme):
    span(start,end)
    if scheme not in ('fbs','fbo'):raise IngestionError('Invalid postings mode')
    rows=[];seen=set()
    for p in objects(postings):
        pn=identifier(p.get('posting_number'))
        if pn in seen:raise IngestionError('Duplicate posting')
        seen.add(pn)
        stamp=(p.get('in_process_at') or p.get('created_at')) if scheme=='fbs' else (p.get('created_at') or p.get('in_process_at'))
        stamp=day(stamp)
        if not start<=stamp<=end:raise IngestionError('Posting date outside requested interval')
        products=objects(p.get('products'))
        if not products:raise IngestionError('Posting without products')
        fin=p.get('financial_data')
        if fin is None:fin={}
        if not isinstance(fin,dict):raise IngestionError('Invalid financial data')
        by_sku={}
        for f in objects(fin.get('products',[])):
            key=identifier(f.get('sku',f.get('product_id')))
            if key in by_sku:raise IngestionError('Duplicate financial product')
            by_sku[key]=commission_value(f)
        keys=[identifier(p.get('sku')) for p in products]
        if len(set(keys))!=len(keys):raise IngestionError('Duplicate product SKU')
        if by_sku and set(by_sku)!=set(keys):raise IngestionError('Commission mapping mismatch')
        total=commission_value(fin)
        if total is not None and by_sku:
            if any(v is None for v in by_sku.values()) or abs(sum(by_sku.values())-total)>.005:raise IngestionError('Commission detail differs from total')
        if total not in (None,0) and not by_sku and len(products)>1:raise IngestionError('Cannot allocate total commission without product detail')
        status=p.get('status') or ''
        if not isinstance(status,str):raise IngestionError('Invalid status')
        raw=encoded(p)
        for item,key in zip(products,keys):
            qty=integer(item.get('quantity'),minimum=1);price=number(item.get('price'))
            if price<0:raise IngestionError('Negative price')
            commission=by_sku.get(key,total if len(products)==1 else (0.0 if total==0 else None))
            rows.append((stamp,pn,key,qty,price,commission,int(status=='cancelled'),int('return' in status.lower()),status,'api' if scheme=='fbs' else 'api_fbo',raw))
    return rows

def replace(con,rows,start,end,*,scheme):
    span(start,end);source='api' if scheme=='fbs' else 'api_fbo'
    if any(len(r)!=11 or r[9]!=source or not start<=r[0]<=end for r in rows):raise IngestionError('Unvalidated rows')
    with atomic(con):
        con.execute('DELETE FROM postings_daily WHERE date BETWEEN ? AND ? AND source=?',(start,end,source))
        con.executemany('INSERT INTO postings_daily(date,posting_number,sku,quantity,price,commission,is_cancelled,is_returned,status,source,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
    return len(rows)
