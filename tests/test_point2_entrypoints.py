"""Check proposed entry functions without importing live module side effects."""
import ast,json,logging,sqlite3,sys
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[1]
def load(path,names):
    tree=ast.parse((ROOT/path).read_text(encoding='utf-8-sig'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==set(names)
    ns=dict(__name__='_candidate_test',__package__='unitka',__file__=str(ROOT/path),sqlite3=sqlite3,sys=sys,json=json,datetime=datetime,timedelta=timedelta,logger=logging.getLogger(__name__))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),path,'exec'),ns);return ns
@pytest.mark.parametrize('module,other',[('unitka/load_postings.py','api_fbo'),('unitka/load_postings_fbo.py','api')])
def test_actual_save_wrapper_keeps_other_source(tmp_path,module,other):
    db=tmp_path/'copy.db'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE postings_daily(date,posting_number,sku,quantity,price,commission,is_cancelled,is_returned,status,source,raw_json)');con.execute('INSERT INTO postings_daily(date,source) VALUES (?,?)',('2026-10-15',other))
    ns=load(module,{'save_postings'});ns['config']=SimpleNamespace(DB_PATH=db);ns['save_postings']([],'2026-10-01','2026-10-31')
    with sqlite3.connect(db) as con:assert con.execute('SELECT source FROM postings_daily').fetchall()==[(other,)]
def test_transaction_wrapper_closes_after_bad_day(tmp_path):
    db=tmp_path/'copy.db'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE finance_transactions(operation_id,date,type,operation_type,amount,posting_number,sku,raw_json,fetched_at)');con.execute("INSERT INTO finance_transactions(operation_id,amount) VALUES ('old',99)")
    con=sqlite3.connect(db);ns=load('unitka/load_transactions.py',{'load_accruals'});ns['connect']=lambda:con;ns['_fetch_accrual_day']=lambda client,day:[{'accrual_id':1,'date':'2026-09-01','total_amount':10}]
    with pytest.raises(ValueError):ns['load_accruals'](None,'2026-10-01','2026-10-01')
    with pytest.raises(sqlite3.ProgrammingError):con.execute('SELECT 1')
    with sqlite3.connect(db) as check:assert check.execute('SELECT operation_id,amount FROM finance_transactions').fetchall()==[('old',99)]
def test_payout_wrapper_empty_success(tmp_path):
    db=tmp_path/'copy.db';sqlite3.connect(db).close();con=sqlite3.connect(db);ns=load('unitka/load_transactions.py',{'load_payouts'});ns['connect']=lambda:con;client=SimpleNamespace(_post=lambda *args:{'result':{'page_count':1,'cash_flows':[],'details':[]}})
    assert ns['load_payouts'](client,'2026-10-01','2026-10-31')==0
    with pytest.raises(sqlite3.ProgrammingError):con.execute('SELECT 1')
def test_ratings_second_chunk_failure_preserves_previous(tmp_path):
    db=tmp_path/'copy.db'
    with sqlite3.connect(db) as con:
        con.executescript('CREATE TABLE postings_daily(sku);CREATE TABLE stock_daily(sku);CREATE TABLE sku_content_rating(sku PRIMARY KEY,content_rating,updated_at);');con.executemany('INSERT INTO postings_daily VALUES (?)',[(str(n),) for n in range(1,102)]);con.execute("INSERT INTO sku_content_rating VALUES ('1',7,'old')")
    calls=[]
    def post(path,body):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('injected')
        return {'products':[{'sku':sku,'rating':99} for sku in body['skus']]}
    ns=load('unitka/load_ratings.py',{'load_content_ratings'});ns['connect']=lambda:sqlite3.connect(db);ns['OzonClient']=lambda:SimpleNamespace(_post=post)
    with pytest.raises(RuntimeError):ns['load_content_ratings']()
    with sqlite3.connect(db) as check:assert check.execute('SELECT * FROM sku_content_rating').fetchall()==[('1',7,'old')]
def test_ad_fetch_failure_before_database():
    ns=load('unitka/load_ads.py',{'main'});calls=[]
    def get(path,**kwargs):
        if path=='/api/client/campaign':return {'list':[{'id':1,'title':'Stopped','state':'STOPPED'}]}
        raise RuntimeError('injected')
    ns['OzonPerformanceClient']=lambda:SimpleNamespace(get=get);ns['connect']=lambda:calls.append('connect');ns['init_db']=lambda:calls.append('init')
    with pytest.raises(RuntimeError):ns['main']()
    assert calls==[]
def test_report_guard_rejects_bad_header():
    ns=load('unitka/load_postings_report.py',{'parse'});ns['_parse_unvalidated_report']=lambda content:(['bad'],[{}])
    with pytest.raises(ValueError):ns['parse'](b'bad')
def test_app_bootstrap_clean_process(tmp_path):
    import os,subprocess
    tree=ast.parse((ROOT/'app/sync_finance.py').read_text(encoding='utf-8-sig'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='save_accrual')
    (tmp_path/'app').mkdir();(tmp_path/'unitka').mkdir();(tmp_path/'unitka/__init__.py').write_text('');(tmp_path/'unitka/accrual_detail.py').write_text('def save_accrual_record(*args):return (1,0)');probe=tmp_path/'app/probe.py';probe.write_text('import sys\n'+ast.unparse(node)+'\nassert save_accrual(None,{}, {}) == (1,0)\n',encoding='utf-8')
    env=os.environ.copy();env.pop('PYTHONPATH',None);run=subprocess.run([sys.executable,'-S',str(probe)],cwd=tmp_path/'app',env=env,capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
