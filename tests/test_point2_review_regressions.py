"""Regression checks for the candidate review findings; no live API or DB."""
import copy,sqlite3
from contextlib import closing
import pytest
from unitka.secondary_ingestion import fetch_returns,ad_rows
from unitka.finance_ingestion import normalize_periods,save_periods,payout_pages
from unitka.postings_ingestion import normalize
A='2026-10-01';B='2026-10-31'
class Client:
    def __init__(self,response):self.response=response
    def _post(self,*a,**k):return copy.deepcopy(self.response)
@pytest.mark.parametrize('response,expected',[
    ({'returns':[]},0),({'returns':[],'last_id':0},0),
    ({'returns':[{'id':1,'created_at':'2026-10-15','product':{'sku':101,'quantity':1,'price':100}}],'last_id':0},1)])
def test_terminal_return_cursor(response,expected):
    assert len(fetch_returns(Client(response),A,B))==expected

def test_missing_ad_money_is_not_zero():
    row={'date':'2026-10-15','campaignId':1,'impressions':0,'clicks':0,'orders':0,'revenue':0}
    with pytest.raises((ValueError,RuntimeError)):ad_rows([row],'1',A,B,'A')

def payout_db():
    con=sqlite3.connect(':memory:')
    con.executescript('CREATE TABLE balance_periods(period_begin,period_end,orders_amount,returns_amount,commission_amount,services_amount,delivery_amount,raw_json,begin_balance,end_balance,payments_total,UNIQUE(period_begin,period_end));CREATE TABLE finance_payouts(payout_id PRIMARY KEY,date,amount,period_from,period_to,status,raw_json,fetched_at);')
    return con

def test_missing_cashflow_money_preserves_previous():
    with closing(payout_db()) as con:
        con.execute('INSERT INTO balance_periods(period_begin,period_end,orders_amount) VALUES (?,?,?)',(A,B,100));con.commit()
        with pytest.raises((ValueError,RuntimeError)):save_periods(con,*normalize_periods([{'cash_flows':[{'period':{'begin':A,'end':B}}],'details':[]}]))
        assert con.execute('SELECT orders_amount FROM balance_periods').fetchone()[0]==100

def test_unrequested_payout_period_cannot_be_replaced():
    raw={'result':{'page_count':1,'cash_flows':[],'details':[{'period':{'begin':'2025-01-01','end':'2025-01-31'},'begin_balance_amount':0,'end_balance_amount':0,'payments':[]}]}}
    with closing(payout_db()) as con:
        con.execute('INSERT INTO finance_payouts(payout_id,period_from,period_to,amount) VALUES (?,?,?,?)',('old','2025-01-01','2025-01-31',55));con.commit()
        with pytest.raises((ValueError,RuntimeError)):save_periods(con,*normalize_periods(payout_pages(Client(raw),A,B)))
        assert con.execute('SELECT COUNT(*) FROM finance_payouts').fetchone()[0]==1

def test_wrong_financial_data_type_rejected():
    p={'posting_number':'P','created_at':'2026-10-15','in_process_at':'2026-10-15','products':[{'sku':101,'quantity':1,'price':100}],'financial_data':[]}
    with pytest.raises((ValueError,RuntimeError)):normalize([p],A,B,scheme='fbs')

def test_ad_explicit_zero_metrics_allowed():
    row={'date':'2026-10-15','campaignId':1,'impressions':0,'clicks':0,'expense':0,'orders':0,'revenue':0}
    values=ad_rows([row],'1',A,B,'A')[0]
    assert values[3:]==(0,0,0.0,0,0.0)

def test_ad_explicit_zero_aliases_allowed():
    row={'date':'2026-10-15','campaignId':1,'impressions':0,'clicks':0,'moneySpent':0,'orderedUnits':0,'orderedRevenue':0}
    assert ad_rows([row],'1',A,B,'A')[0][3:]==(0,0,0.0,0,0.0)

def test_overlapping_cashflow_period_allowed():
    raw={'result':{'page_count':1,'cash_flows':[],'details':[{'period':{'begin':'2026-09-28','end':'2026-10-04'},'begin_balance_amount':0,'end_balance_amount':0,'payments':[]}]}}
    assert len(payout_pages(Client(raw),A,B))==1

def test_boolean_cursor_not_a_terminal_id():
    with pytest.raises((ValueError,RuntimeError)):fetch_returns(Client({'returns':[],'last_id':False}),A,B)
