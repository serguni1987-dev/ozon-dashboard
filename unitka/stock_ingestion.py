"""Complete stock collection before transactional replacement."""
from .ingestion_safety import IngestionError,integer,identifier,objects,cursor_pages,atomic

def collect(fetch):
    offers=[];daily={};seen=set()
    for item in cursor_pages(fetch,'items',allow_empty=False,page_size=1000):
        offer=identifier(item.get('offer_id'))
        if offer in seen:raise IngestionError('Duplicate stock offer')
        seen.add(offer);product=integer(item.get('product_id'),minimum=1);totals=[0,0,0,0]
        for stock in objects(item.get('stocks')):
            typ=stock.get('type')
            if typ not in ('fbo','fbs'):raise IngestionError('Unsupported stock type')
            present=integer(stock.get('present'));reserved=integer(stock.get('reserved'));idx=0 if typ=='fbo' else 2
            totals[idx]+=present;totals[idx+1]+=reserved
            if stock.get('sku') is not None:
                agg=daily.setdefault(identifier(stock['sku']),[0,0,0,0]);agg[idx]+=present;agg[idx+1]+=reserved
            elif present or reserved:daily[None]=None
        offers.append((offer,product,*totals,sum(totals[::2]),sum(totals[1::2])))
    return offers,daily

def replace_current(con,rows,stamp,*,allow_large_drop=False):
    if not rows:raise IngestionError('Empty stock snapshot')
    with atomic(con):
        old=con.execute('SELECT COUNT(*) FROM current_stocks').fetchone()[0]
        if not allow_large_drop and len(rows)<old*.8:raise IngestionError('Stock count dropped more than 20%')
        con.execute('DELETE FROM current_stocks')
        con.executemany('INSERT INTO current_stocks(offer_id,sku,fbo_present,fbo_reserved,fbs_present,fbs_reserved,total_present,total_reserved,fetched_at) VALUES (?,?,?,?,?,?,?,?,?)',[(*r,stamp) for r in rows])
    return len(rows)

def replace_daily(con,daily,day):
    if None in daily or not daily:raise IngestionError('Missing marketplace SKU or empty daily snapshot')
    with atomic(con):
        old=con.execute('SELECT COUNT(*) FROM stock_daily WHERE date=?',(day,)).fetchone()[0]
        if len(daily)<old*.8:raise IngestionError('Daily stock count dropped more than 20%')
        con.execute('DELETE FROM stock_daily WHERE date=?',(day,))
        con.executemany('INSERT INTO stock_daily(date,sku,fbo_present,fbo_reserved,fbs_present,fbs_reserved) VALUES (?,?,?,?,?,?)',[(day,sku,*agg) for sku,agg in daily.items()])
    return len(daily)
