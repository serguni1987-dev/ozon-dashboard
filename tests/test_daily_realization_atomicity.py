"""Daily-loader regressions. AST loading prevents imports/config/network side effects."""
import ast
import copy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import pytest

SCHEMA = 'CREATE TABLE realization_daily (\n  id              INTEGER PRIMARY KEY,\n  date            TEXT NOT NULL,\n  accrual_id      INTEGER,\n  posting_number  TEXT,\n  sku             INTEGER NOT NULL,\n  offer_id        TEXT,\n  quantity        INTEGER DEFAULT 0,\n  seller_price    REAL DEFAULT 0,\n  sale_price      REAL DEFAULT 0,\n  sale_amount     REAL DEFAULT 0,\n  bonus           REAL DEFAULT 0,\n  coinvestment    REAL DEFAULT 0,\n  commission      REAL DEFAULT 0,\n  commission_ratio REAL DEFAULT 0,\n  delivery_total  REAL DEFAULT 0,\n  is_return       INTEGER DEFAULT 0,\n  raw_json        TEXT,\n  fetched_at      TEXT,\n  UNIQUE(date, accrual_id, posting_number, sku)\n);\nCREATE TABLE accrual_sku_daily (\n  id             INTEGER PRIMARY KEY,\n  date           TEXT NOT NULL,\n  accrual_id     INTEGER,\n  posting_number TEXT,\n  sku            INTEGER NOT NULL,\n  type_id        INTEGER NOT NULL,\n  amount         REAL NOT NULL,\n  raw_json       TEXT,\n  fetched_at     TEXT,\n  UNIQUE(date, accrual_id, posting_number, sku, type_id)\n);\nCREATE TABLE accrual_non_item_daily (\n  id             INTEGER PRIMARY KEY,\n  date           TEXT NOT NULL,\n  accrual_id     INTEGER,\n  posting_number TEXT,\n  type_id        INTEGER NOT NULL,\n  amount         REAL NOT NULL,\n  kind           TEXT,\n  raw_json       TEXT,\n  fetched_at     TEXT,\n  UNIQUE(date, accrual_id, posting_number, type_id, kind)\n);\nCREATE TABLE load_log (\n  id          INTEGER PRIMARY KEY,\n  date        TEXT NOT NULL UNIQUE,\n  status      TEXT,\n  n_accruals  INTEGER DEFAULT 0,\n  n_rows      INTEGER DEFAULT 0,\n  error       TEXT,\n  fetched_at  TEXT\n);'
DAY = "2026-08-01"
ROOT = Path(__file__).resolve().parents[1]

def load_code(path, classes=False):
    tree=ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes=[]
    for node in tree.body:
        if isinstance(node,ast.Import):
            if all(alias.name.split('.')[0] in {'json','re','argparse','time','urllib'} for alias in node.names):nodes.append(node)
        elif isinstance(node,ast.ImportFrom):
            if node.level==0 and node.module=='datetime':nodes.append(node)
        elif isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            nodes.append(node)
        elif isinstance(node,ast.Assign):
            if any(isinstance(t,ast.Name) and t.id=='_NUM_RE' for t in node.targets):nodes.append(node)
    ns={'__name__':'_offline_daily_test'}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns

@pytest.fixture
def loader():return load_code(ROOT/'unitka'/'load_realization_daily.py')

@pytest.fixture
def con():
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.executescript(SCHEMA)
    yield c
    c.close()

class Client:
    def __init__(self,rows=None,error=None):self.rows=rows;self.error=error;self.calls=0
    def accrual_by_day_all(self,day):
        self.calls+=1
        if self.error:raise self.error
        return copy.deepcopy(self.rows)

def fee(ident=1,amount='-3.42',day=DAY):
    return {'accrual_id':ident,'date':day,'non_item_fee':{'type_id':76,'accrued':{'amount':amount}}}

def product(ident=2,day=DAY):
    return {'accrual_id':ident,'date':day,'posting':{'products':[
        {'sku':123,'quantity':1,'commission':{'sale_price':{'amount':'100'}},
         'delivery':{'services':[{'type_id':32,'accrued':{'amount':'-10'}}]}}]}}

def state(c):
    return {t:[tuple(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY id')]
            for t in ('realization_daily','accrual_sku_daily','accrual_non_item_daily')}

def run(loader,c,rows,force=True):return loader['load_day'](Client(rows),c,DAY,force)

def test_null_posting_repeated_direct_call_is_idempotent(loader,con):
    for _ in range(3):loader['process_accrual'](con,DAY,fee(),'now')
    assert tuple(con.execute('SELECT count(*),sum(amount) FROM accrual_non_item_daily').fetchone())==(1,-3.42)
    assert con.in_transaction

def test_forced_repeat_of_day_does_not_duplicate(loader,con):
    for _ in range(3):assert 'error' not in run(loader,con,[fee(),product()])
    assert [con.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('realization_daily','accrual_sku_daily','accrual_non_item_daily')]==[1,1,1]
    assert not con.in_transaction

def test_changed_fee_replaces_old_value(loader,con):
    run(loader,con,[fee()]);run(loader,con,[fee(amount='-8')])
    assert tuple(con.execute('SELECT count(*),sum(amount) FROM accrual_non_item_daily').fetchone())==(1,-8)

def test_removed_operation_does_not_survive_complete_reload(loader,con):
    run(loader,con,[fee(),product()]);run(loader,con,[fee()])
    assert con.execute('SELECT count(*) FROM realization_daily').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM accrual_sku_daily').fetchone()[0]==0

def test_valid_empty_response_clears_only_requested_day(loader,con):
    run(loader,con,[fee()]);loader['process_accrual'](con,'2026-08-02',fee(9,day='2026-08-02'),'now');con.commit()
    result=run(loader,con,[])
    assert result['accruals']==0
    assert tuple(con.execute('SELECT date,count(*) FROM accrual_non_item_daily GROUP BY date').fetchone())==('2026-08-02',1)

def test_skip_ok_day_does_not_call_api(loader,con):
    run(loader,con,[fee()]);client=Client(error=AssertionError('must not call'))
    assert loader['load_day'](client,con,DAY)=={'date':DAY,'skipped':True}
    assert client.calls==0

def test_row_failure_restores_previous_day(loader,con,monkeypatch):
    run(loader,con,[fee(),product()]);before=state(con)
    original=loader['_process_accrual_rows']
    def fail_second(c,day,acc,now):
        result=original(c,day,acc,now)
        if acc['accrual_id']==2:raise RuntimeError('injected after writing')
        return result
    monkeypatch.setitem(loader,'_process_accrual_rows',fail_second)
    result=run(loader,con,[fee(amount='-9'),product()])
    assert 'error' in result and state(con)==before
    assert con.execute('SELECT status FROM load_log WHERE date=?',(DAY,)).fetchone()[0]=='error'
    assert not con.in_transaction

def test_api_failure_preserves_old_rows(loader,con):
    run(loader,con,[fee()]);before=state(con)
    result=loader['load_day'](Client(error=RuntimeError('network')),con,DAY,True)
    assert 'error' in result and state(con)==before

def test_success_does_not_commit_outer_transaction(loader,con):
    con.execute('CREATE TABLE unrelated(x INTEGER)');con.execute('INSERT INTO unrelated VALUES (1)')
    assert 'error' not in run(loader,con,[fee()]) and con.in_transaction
    con.rollback()
    assert con.execute('SELECT count(*) FROM unrelated').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM accrual_non_item_daily').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM load_log').fetchone()[0]==0

def test_failure_does_not_commit_or_rollback_unrelated_outer_work(loader,con):
    con.execute('CREATE TABLE unrelated(x INTEGER)');con.execute('INSERT INTO unrelated VALUES (1)')
    assert 'error' in run(loader,con,[fee(day='2026-08-02')])
    assert con.in_transaction and con.execute('SELECT count(*) FROM unrelated').fetchone()[0]==1
    con.rollback()
    assert con.execute('SELECT count(*) FROM unrelated').fetchone()[0]==0

def test_direct_row_failure_restores_existing_operation(loader,con,monkeypatch):
    loader['process_accrual'](con,DAY,fee(),'now');con.commit();before=state(con)
    def fail(c,day,acc,now):raise ValueError('injected')
    monkeypatch.setitem(loader,'_process_accrual_rows',fail)
    with pytest.raises(ValueError):loader['process_accrual'](con,DAY,fee(amount='-8'),'now')
    assert state(con)==before and not con.in_transaction

@pytest.mark.parametrize('bad',[None,{},'bad',[None],[{'accrual_id':1,'date':'2026-08-02'}],
    [{'accrual_id':0,'date':DAY}],[{'accrual_id':True,'date':DAY}],
    [{'accrual_id':None,'date':DAY}],[{'accrual_id':1,'date':DAY,'x':float('nan')}],
    [fee(),fee()],[fee(1),fee('01')]])
def test_invalid_response_preserves_old_data(loader,con,bad):
    run(loader,con,[fee()]);before=state(con)
    assert 'error' in run(loader,con,bad)
    assert state(con)==before

def test_error_log_write_failure_still_rolls_back_data(loader,con):
    run(loader,con,[fee()]);before=state(con)
    con.execute("CREATE TRIGGER reject_log BEFORE INSERT ON load_log BEGIN SELECT RAISE(ABORT,'log failed'); END")
    with pytest.raises(sqlite3.IntegrityError):run(loader,con,[fee(amount='-9')])
    assert state(con)==before

def test_main_stops_after_failed_day(loader,monkeypatch):
    args=SimpleNamespace(single=None,date_from='2026-08-01',date_to='2026-08-03',force=True)
    seen=[]
    monkeypatch.setitem(loader,'parse_args',lambda:args)
    monkeypatch.setitem(loader,'config',SimpleNamespace(check_credentials=lambda:None))
    monkeypatch.setitem(loader,'db',SimpleNamespace(connect=lambda:object(),init_schema=lambda c:None))
    monkeypatch.setitem(loader,'OzonClient',lambda:object())
    def fail(client,c,day,force=False):seen.append(day);return {'date':day,'error':'injected'}
    monkeypatch.setitem(loader,'load_day',fail)
    with pytest.raises(RuntimeError):loader['main']()
    assert seen==['2026-08-01']

def pagination_client(pages):
    ns=load_code(ROOT/'unitka'/'ozon_client.py',True)
    client=object.__new__(ns['OzonClient']);responses=iter(pages)
    client.accrual_by_day=lambda day,cursor:next(responses)
    return client,ns['OzonError']

def test_pagination_collects_all_pages():
    client,_=pagination_client([{'accruals':[fee()],'last_id':'next'},{'accruals':[product()]}])
    assert len(client.accrual_by_day_all(DAY))==2

@pytest.mark.parametrize('pages',[
    [{}],[{'accruals':None}],[{'accruals':{}}],[{'accruals':[None]}],
    [{'accruals':[],'last_id':'next'}],
    [{'accruals':[fee()],'last_id':'same'},{'accruals':[fee()],'last_id':'same'}],
    [{'accruals':[fee()],'last_id':[]}],
    [{'accruals':[fee()],'last_id':'next'},{}]])
def test_invalid_or_repeated_page_never_returns_partial_list(pages):
    client,error=pagination_client(pages)
    with pytest.raises(error):client.accrual_by_day_all(DAY)

def test_pagination_allows_valid_empty_day():
    client,_=pagination_client([{'accruals':[]}])
    assert client.accrual_by_day_all(DAY)==[]

def test_pagination_limit():
    client,error=pagination_client([{'accruals':[fee()],'last_id':str(i+1)} for i in range(200)])
    with pytest.raises(error,match='limit'):client.accrual_by_day_all(DAY)
