"""Exercise the financial orchestrator with dependency stubs only."""
import argparse,ast,logging,sys,types
from datetime import datetime,timedelta
from pathlib import Path
import pytest
from unittest.mock import Mock

STAGES=['load_transactions','load_stocks','calc_receivables','calc_balance','calc_taxes','calc_cashflow','calc_working_capital','calc_money_in_goods','calc_dashboard']
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def pipeline(monkeypatch):
    tree=ast.parse((ROOT/'unitka/run_finance.py').read_text(encoding='utf-8-sig'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'step','main'}]
    assert {n.name for n in nodes}=={'step','main'}
    package=types.ModuleType('_point2_pipeline_stub');package.__path__=[]
    ns={'__name__':'_point2_pipeline_target','__package__':package.__name__,'argparse':argparse,
        'sys':sys,'datetime':datetime,'timedelta':timedelta,'logger':Mock()}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'pipeline_target','exec'),ns)
    def run(failure=None,value=None,mode='exception',skip=False,zero=False):
        calls=[];arguments={}
        for name in STAGES:
            def invoke(*a,_name=name,**kw):
                calls.append(_name);arguments[_name]=(a,kw)
                if _name==failure:
                    if mode=='exception':raise RuntimeError('injected loader/stage failure')
                    if mode=='exit':raise SystemExit(2)
                    return value
                return 0 if zero else None
            setattr(package,name,types.SimpleNamespace(**{('load_stocks' if name=='load_stocks' else 'main'):invoke}))
        argv=['run_finance.py','--from','2026-10-01','--to','2026-10-31']+(['--skip-fetch'] if skip else [])
        with monkeypatch.context() as context:
            context.setitem(sys.modules,package.__name__,package);context.setattr(sys,'argv',argv)
            try:ns['main']();code=0
            except SystemExit as exc:code=exc.code
        return code,calls,arguments
    return run

@pytest.mark.parametrize('failure',STAGES)
def test_exception_stops_all_following_stages(pipeline,failure):
    code,calls,_=pipeline(failure)
    assert code==1
    assert calls==STAGES[:STAGES.index(failure)+1]

@pytest.mark.parametrize('failure',STAGES[:2])
def test_false_loader_result_stops_calculations(pipeline,failure):
    code,calls,_=pipeline(failure,value=False,mode='return')
    assert code==1 and calls==STAGES[:STAGES.index(failure)+1]

@pytest.mark.parametrize('failure',STAGES[:2])
@pytest.mark.parametrize('status',['ERROR','FAIL','FAILED','PARTIAL','INCOMPLETE','SKIPPED'])
def test_unsuccessful_loader_status_stops_calculations(pipeline,failure,status):
    code,calls,_=pipeline(failure,value={'status':status},mode='return')
    assert code==1 and calls==STAGES[:STAGES.index(failure)+1]

def test_success_preserves_order_and_call_arguments(pipeline):
    code,calls,args=pipeline()
    assert code==0 and calls==STAGES
    assert args['load_transactions']==(('2026-10-01','2026-10-31'),{})
    assert args['calc_receivables']==(('2026-10-01','2026-10-31',False),{})

def test_explicit_skip_fetch_preserves_calculation_mode(pipeline):
    code,calls,_=pipeline(skip=True)
    assert code==0 and calls==STAGES[2:]

def test_numeric_zero_is_not_boolean_false(pipeline):
    code,calls,_=pipeline(zero=True)
    assert code==0 and calls==STAGES

def test_direct_system_exit_stops_chain(pipeline):
    code,calls,_=pipeline('load_transactions',mode='exit')
    assert code==2 and calls==['load_transactions']
