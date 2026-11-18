import logging
from datetime import datetime
from .ozon_client import OzonClient
from .log_change import log_change
from .db import connect

logger = logging.getLogger(__name__)

def load_stocks():
    from .stock_ingestion import collect,replace_daily
    client=OzonClient();_,daily=collect(lambda cursor:client._post('/v4/product/info/stocks',{'filter':{'visibility':'ALL'},'cursor':cursor,'limit':1000}))
    conn=connect();today=datetime.now().strftime('%Y-%m-%d');changes=[]
    try:
        for sku,agg in daily.items():
            if sku is None:continue
            row=conn.execute('SELECT fbo_present+fbs_present FROM stock_daily WHERE sku=? AND date<? ORDER BY date DESC LIMIT 1',(sku,today)).fetchone();old=row[0] if row else 0;new=agg[0]+agg[2]
            if abs(new-old)>10:changes.append((sku,old,new))
        count=replace_daily(conn,daily,today)
    finally:conn.close()
    warnings=[]
    for sku,old,new in changes:
        try:log_change(sku,'stock',old,new,source='auto',comment='Stock snapshot changed')
        except Exception as exc:warnings.append(type(exc).__name__)
    if warnings:logger.warning('Snapshot saved; non-authoritative change-log failures: %s',warnings)
    return {'status':'OK','rows':count,'log_warnings':warnings}

if __name__ == '__main__':
    load_stocks()
