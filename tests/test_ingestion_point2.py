"""Offline regression tests for the point-2 candidate."""
import copy,sqlite3
import pytest
from unitka.ingestion_safety import IngestionError,number,integer,span,cursor_pages
from unitka.postings_ingestion import commission_value,fetch,normalize,replace
from unitka.stock_ingestion import collect,replace_current,replace_daily
from unitka.finance_ingestion import parse_accrual,validated_day,payout_pages,normalize_periods,save_periods
from unitka.secondary_ingestion import parse_return,fetch_returns,campaign_list,ad_rows
A='2026-10-01';B='2026-10-31'
class Client:
    def __init__(self,pages):self.pages=iter(pages)
    def _post(self,*args,**kwargs):
        result=next(self.pages)
        if isinstance(result,Exception):raise result
        return copy.deepcopy(result)
def posting(q=1):return dict(posting_number='P',created_at='2026-10-15',in_process_at='2026-10-15',status='delivered',products=[{'sku':101,'quantity':q,'price':100},{'sku':102,'quantity':1,'price':200}],financial_data={'commission_amount':-30,'products':[{'product_id':101,'commission_amount':-10},{'product_id':102,'commission_amount':-20}]})
@pytest.mark.parametrize('bad',[None,True,'bad','NaN','Infinity',float('-inf'),{},[]])
def test_money_rejects_bad(bad):
    with pytest.raises(IngestionError):number(bad)
@pytest.mark.parametrize('bad',[None,True,-1,1.5,'NaN',9223372036854775808])
def test_integer_rejects_bad(bad):
    with pytest.raises(IngestionError):integer(bad)
def test_integer_precision():assert integer('9007199254740993')==9007199254740993
@pytest.mark.parametrize('a,b',[('2026-10-32',B),(B,A),('2026-1-1',B)])
def test_bad_dates(a,b):
    with pytest.raises(IngestionError):span(a,b)
@pytest.mark.parametrize('amount',[-30,0,30])
@pytest.mark.parametrize('mode',['flat','nested','both'])
def test_commission_formats(amount,mode):
    record={}
    if mode in ('flat','both'):record['commission_amount']=amount
    if mode in ('nested','both'):record['commission']={'amount':amount,'percent':40,'currency':'RUB'}
    assert commission_value(record)==amount
@pytest.mark.parametrize('nested',[{'amount':'NaN'},{'amount':'bad'},{'percent':40},[],True])
def test_bad_nested_fee(nested):
    with pytest.raises(IngestionError):commission_value({'commission':nested})
def test_conflicting_fees():
    with pytest.raises(IngestionError):commission_value({'commission_amount':0,'commission':{'amount':-30}})
def test_absent_fee_unknown():assert commission_value({}) is None
@pytest.mark.parametrize('scheme',['fbs','fbo'])
@pytest.mark.parametrize('nested',[False,True])
def test_fee_not_duplicated_or_quantity_multiplied(scheme,nested):
    p=posting(2)
    if nested:
        for item in p['financial_data']['products']:item['commission']={'amount':item.pop('commission_amount')}
    rows=normalize([p],A,B,scheme=scheme)
    assert sum(r[5] for r in rows)==-30 and rows[0][3]==2
@pytest.mark.parametrize('response',[{},None,{'postings':None},{'postings':[]},{'postings':[],'has_next':True},{'postings':{},'has_next':False}])
def test_bad_fbs(response):
    with pytest.raises(IngestionError):fetch(Client([response]),A,B,scheme='fbs',limit=100)
@pytest.mark.parametrize('response',[{},None,{'result':None},{'result':{}},{'result':[None]}])
def test_bad_fbo(response):
    with pytest.raises(IngestionError):fetch(Client([response]),A,B,scheme='fbo',limit=1000)
@pytest.mark.parametrize('scheme,response',[('fbs',{'postings':[],'has_next':False}),('fbo',{'result':[]})])
def test_valid_empty_postings(scheme,response):assert fetch(Client([response]),A,B,scheme=scheme,limit=100)==[]
def test_repeated_page():
    with pytest.raises(IngestionError):fetch(Client([{'postings':[posting()],'has_next':True}]*2),A,B,scheme='fbs',limit=1)
@pytest.mark.parametrize('scheme',['fbs','fbo'])
def test_wrong_posting_period(scheme):
    p=posting();p['created_at']=p['in_process_at']='2026-09-30'
    with pytest.raises(IngestionError):normalize([p],A,B,scheme=scheme)
@pytest.mark.parametrize('q',[0,-1,1.5,None])
def test_bad_product_quantity(q):
    with pytest.raises(IngestionError):normalize([posting(q)],A,B,scheme='fbs')
def test_unattributed_total_rejected():
    p=posting();del p['financial_data']['products']
    with pytest.raises(IngestionError):normalize([p],A,B,scheme='fbs')
def db_postings():
    c=sqlite3.connect(':memory:');c.execute('CREATE TABLE postings_daily(date,posting_number,sku,quantity,price,commission,is_cancelled,is_returned,status,source,raw_json)')
    for source in ('api','api_fbo','xlsx_report'):c.execute('INSERT INTO postings_daily(date,source) VALUES (?,?)',('2026-10-15',source))
    c.commit();return c
@pytest.mark.parametrize('scheme,other',[('fbs','api_fbo'),('fbo','api')])
def test_repeat_preserves_other_source(scheme,other):
    c=db_postings()
    try:
        rows=normalize([posting()],A,B,scheme=scheme)
        for _ in range(2):replace(c,rows,A,B,scheme=scheme)
        assert c.execute('SELECT COUNT(*) FROM postings_daily WHERE source=?',(other,)).fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM postings_daily WHERE source='xlsx_report'").fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM postings_daily').fetchone()[0]==4
    finally:c.close()
def test_posting_write_rollback():
    c=db_postings()
    try:
        before=c.execute('SELECT * FROM postings_daily').fetchall();c.execute("CREATE TRIGGER fail BEFORE INSERT ON postings_daily BEGIN SELECT RAISE(ABORT,'injected'); END")
        with pytest.raises(sqlite3.IntegrityError):replace(c,normalize([posting()],A,B,scheme='fbs'),A,B,scheme='fbs')
        assert c.execute('SELECT * FROM postings_daily').fetchall()==before
    finally:c.close()
def test_outer_rollback():
    c=db_postings()
    try:
        c.execute("INSERT INTO postings_daily(date,source) VALUES ('2025-01-01','marker')");replace(c,[],A,B,scheme='fbs');assert c.in_transaction;c.rollback()
        assert c.execute('SELECT COUNT(*) FROM postings_daily').fetchone()[0]==3
    finally:c.close()
def stock():return {'offer_id':'A','product_id':1,'stocks':[{'sku':101,'type':'fbs','present':3,'reserved':0},{'sku':101,'type':'fbs','present':4,'reserved':1}]}
@pytest.mark.parametrize('pages',[[{}],[{'items':None}],[{'items':[],'cursor':'x'}],[{'items':[{}],'cursor':'x'},{'items':[{}],'cursor':'x'}],[{'items':[{}],'cursor':'','last_id':'x'}]])
def test_bad_stock_pages(pages):
    it=iter(pages)
    with pytest.raises(IngestionError):collect(lambda c:next(it))
def test_stock_sum():
    offers,daily=collect(lambda c:{'items':[stock()]})
    assert offers[0][4:8]==(7,1,7,1) and daily['101']==[0,0,7,1]
def test_no_sku_guess():
    item=stock();[r.pop('sku') for r in item['stocks']];_,daily=collect(lambda c:{'items':[item]});c=sqlite3.connect(':memory:')
    try:
        with pytest.raises(IngestionError):replace_daily(c,daily,'2026-10-15')
    finally:c.close()
def test_empty_stock_rejected():
    with pytest.raises(IngestionError):collect(lambda c:{'items':[]})
def test_page_limit():
    it=iter([{'items':[{}],'cursor':str(n)} for n in range(3)])
    with pytest.raises(IngestionError,match='limit'):cursor_pages(lambda c:next(it),'items',max_pages=3)
def test_snapshot_fetch_failure_preserves_old():
    c=sqlite3.connect(':memory:');c.execute('CREATE TABLE current_stocks(offer_id,sku,fbo_present,fbo_reserved,fbs_present,fbs_reserved,total_present,total_reserved,fetched_at)');c.execute("INSERT INTO current_stocks(offer_id,total_present) VALUES ('old',7)");c.commit()
    try:
        def failed(c):raise RuntimeError('HTTP 500')
        with pytest.raises(RuntimeError):
            rows,_=collect(failed);replace_current(c,rows,'now')
        assert c.execute('SELECT offer_id,total_present FROM current_stocks').fetchall()==[('old',7)]
    finally:c.close()
def accrual():return {'accrual_id':1,'date':'2026-10-15','total_amount':{'amount':'10'},'unit_number':'U','posting':{'products':[{'sku':1},{'sku':2}]}}
@pytest.mark.parametrize('key,value',[('accrual_id',None),('accrual_id',0),('accrual_id',True),('total_amount',{'amount':'bad'}),('total_amount',{'amount':'NaN'}),('date','2026-10-99')])
def test_bad_accrual(key,value):
    row=accrual();row[key]=value
    with pytest.raises(IngestionError):parse_accrual(row)
def test_wrong_accrual_day():
    with pytest.raises(IngestionError):validated_day([accrual()],'2026-10-16')
def test_duplicate_accrual():
    with pytest.raises(IngestionError):validated_day([accrual(),accrual()],'2026-10-15')
def test_accrual_metadata():
    row=parse_accrual(accrual());assert row['posting_number']=='U' and row['sku'] is None and row['amount']==10

def payments(values):return [{'cash_flows':[],'details':[{'period':{'begin':A,'end':B},'begin_balance_amount':0,'end_balance_amount':0,'payments':[{'payment':v,'currency_code':'RUB'} for v in values]}]}]
def payout_db():
    c=sqlite3.connect(':memory:');c.executescript('CREATE TABLE balance_periods(period_begin,period_end,orders_amount,returns_amount,commission_amount,services_amount,delivery_amount,raw_json,begin_balance,end_balance,payments_total,UNIQUE(period_begin,period_end)); CREATE TABLE finance_payouts(payout_id PRIMARY KEY,date,amount,period_from,period_to,status,raw_json,fetched_at);');return c

def test_payout_old_tail_removed():
    c=payout_db()
    try:
        save_periods(c,*normalize_periods(payments([-10,-20])));save_periods(c,*normalize_periods(payments([-10])));assert c.execute('SELECT COUNT(*),SUM(amount) FROM finance_payouts').fetchone()==(1,10)
    finally:c.close()
def test_payment_order_stable():
    c=payout_db()
    try:
        save_periods(c,*normalize_periods(payments([-10,-20])));before=c.execute('SELECT payout_id,amount FROM finance_payouts ORDER BY payout_id').fetchall();save_periods(c,*normalize_periods(payments([-20,-10])))
        assert c.execute('SELECT payout_id,amount FROM finance_payouts ORDER BY payout_id').fetchall()==before
    finally:c.close()
def test_positive_payment_requires_review():
    with pytest.raises(IngestionError):normalize_periods(payments([10]))
def test_bad_payout_second_page():
    with pytest.raises(RuntimeError):payout_pages(Client([{'result':{'page_count':2,'cash_flows':[],'details':[]}},None]),A,B)
def returned():return {'return_id':1,'created_at':'2026-10-15','product':{'sku':101,'quantity':1,'price':'100'}}
def test_bad_return_money():
    row=returned();row['product']['price']='bad'
    with pytest.raises(IngestionError):parse_return(row)
def test_repeated_return_cursor():
    with pytest.raises(IngestionError):fetch_returns(Client([{'returns':[returned()],'last_id':1}]*2),A,B)
def test_stopped_campaign_not_filtered():assert campaign_list({'list':[{'id':1,'title':'Stopped','state':'STOPPED'}]})=={'1':'Stopped'}
@pytest.mark.parametrize('raw',[{},None,{'rows':None},{'rows':[],'cursor':'next'}])
def test_bad_ad_response(raw):
    with pytest.raises(IngestionError):ad_rows(raw,'1',A,B,'A')
def test_zero_not_replaced_by_alias():assert ad_rows([{'date':'2026-10-15','expense':0,'moneySpent':99,'impressions':0,'clicks':0,'orders':0,'revenue':0}],'1',A,B,'A')[0][5]==0
