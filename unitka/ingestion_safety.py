"""Strict ingestion primitives, without configuration/network side effects."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal,InvalidOperation
import json,math
class IngestionError(ValueError):pass

def number(value,*,missing=False):
    if isinstance(value,dict):
        if 'amount' not in value:raise IngestionError('Amount object without amount')
        value=value['amount']
    if value is None:
        if missing:return 0.0
        raise IngestionError('Required amount missing')
    if isinstance(value,bool):raise IngestionError('Boolean number')
    try:result=float(value)
    except (TypeError,ValueError,OverflowError) as exc:raise IngestionError('Invalid number') from exc
    if not math.isfinite(result):raise IngestionError('Non-finite number')
    return result

def integer(value,*,minimum=0):
    if value is None or isinstance(value,bool):raise IngestionError('Invalid integer')
    try:result=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as exc:raise IngestionError('Invalid integer') from exc
    if not result.is_finite() or result!=int(result) or not minimum<=result<=9223372036854775807:raise IngestionError('Invalid integer')
    return int(result)

def identifier(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)):raise IngestionError('Invalid identifier')
    result=str(value)
    if not result or result!=result.strip() or result in {'None','0'}:raise IngestionError('Missing identifier')
    return result

def day(value):
    if not isinstance(value,str):raise IngestionError('Missing date')
    part=value[:10]
    try:parsed=date.fromisoformat(part)
    except ValueError as exc:raise IngestionError('Invalid date') from exc
    if parsed.isoformat()!=part:raise IngestionError('Invalid ISO date')
    return part

def span(a,b):
    if day(a)!=a or day(b)!=b or a>b:raise IngestionError('Invalid date interval')
    return a,b

def objects(value):
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):raise IngestionError('Expected object array')
    return value

def encoded(value):
    try:return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True)
    except (TypeError,ValueError) as exc:raise IngestionError('Invalid JSON values') from exc

@contextmanager
def atomic(con):
    con.execute('SAVEPOINT ingestion_write')
    try:
        yield
        con.execute('RELEASE ingestion_write')
    except BaseException:
        con.execute('ROLLBACK TO ingestion_write');con.execute('RELEASE ingestion_write');raise

def cursor_pages(fetch,key,*,max_pages=200,allow_empty=True,page_size=None):
    if type(max_pages) is not int or max_pages<1:raise IngestionError('Invalid page limit')
    rows=[];cursor='';seen=set()
    for _ in range(max_pages):
        response=fetch(cursor)
        if not isinstance(response,dict) or key not in response:raise IngestionError('Missing response rows')
        batch=objects(response[key])
        if page_size and len(batch)>page_size:raise IngestionError('Page exceeds requested size')
        if response.get('cursor') is not None and response.get('last_id') not in (None,'',response.get('cursor')):raise IngestionError('Contradictory cursors')
        nxt=response.get('cursor',response.get('last_id',''))
        if nxt is None:nxt=''
        if not isinstance(nxt,(str,int)) or isinstance(nxt,bool):raise IngestionError('Invalid cursor')
        nxt=str(nxt)
        if not batch and nxt:raise IngestionError('Empty page with continuation')
        rows.extend(batch)
        if not nxt:
            if response.get('has_next') is True:raise IngestionError('Missing continuation cursor')
            if page_size and len(batch)==page_size and response.get('has_next') is not False:raise IngestionError('Full final page without completion evidence')
            if not rows and not allow_empty:raise IngestionError('Empty snapshot requires review')
            return rows
        if nxt==cursor or nxt in seen:raise IngestionError('Repeated cursor')
        seen.add(nxt);cursor=nxt
    raise IngestionError('Incomplete fetch: page limit')
