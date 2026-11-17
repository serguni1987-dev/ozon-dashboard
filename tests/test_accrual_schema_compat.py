"""Compatibility regressions for the accrual item reader; no services or DB files."""
import json
import sqlite3
import pytest
from unitka.accrual_detail import iter_accrual_products

MINIMAL = """CREATE TABLE accruals(date TEXT, sku INTEGER, accrued_category TEXT,
    sale_price REAL, bonus REAL, coinvestment REAL, sale_commission REAL)"""

def minimal():
    con = sqlite3.connect(":memory:")
    con.execute(MINIMAL)
    con.executemany("INSERT INTO accruals VALUES (?,1,'POSTING',?,0,0,?)",[
        ('2026-10-15',1000,-100),('2026-10-20',-1000,100)])
    return con

def rows(con,a='2026-10-01',b='2026-11-01'):
    return list(iter_accrual_products(con.cursor(),a,b))

def test_minimal_schema_without_seller_raw_or_id():
    con=minimal()
    try:
        result=rows(con)
        assert len(result)==2
        assert sum(r['sale_price'] for r in result)==0
        assert result[0]['seller_price']==0
        assert result[0]['quantity']==1
    finally:con.close()

def test_minimal_query_only():
    con=minimal()
    try:
        con.execute('PRAGMA query_only=ON')
        assert len(rows(con))==2
    finally:con.close()

def test_minimal_half_open_interval():
    con=minimal()
    try:
        result=rows(con,'2026-10-15','2026-10-20')
        assert len(result)==1 and result[0]['sale_price']==1000
    finally:con.close()

def test_minimal_empty_interval():
    con=minimal()
    try:assert rows(con,'2026-10-15','2026-10-15')==[]
    finally:con.close()

def test_json_still_has_priority_without_seller_price_or_id():
    con=minimal()
    try:
        con.execute('ALTER TABLE accruals ADD COLUMN raw_json TEXT')
        raw=json.dumps({'posting':{'products':[
            {'sku':1,'quantity':2,'commission':{'sale_price':{'amount':'300'}}},
            {'sku':2,'quantity':1,'commission':{'sale_price':{'amount':'200'}}}]}})
        con.execute("UPDATE accruals SET raw_json=? WHERE date='2026-10-15'",(raw,))
        result=rows(con,'2026-10-15','2026-10-16')
        assert [(r['sku'],r['quantity'],r['sale_price']) for r in result]==[(1,2,300),(2,1,200)]
    finally:con.close()

def test_invalid_json_is_not_silently_ignored():
    con=minimal()
    try:
        con.execute('ALTER TABLE accruals ADD COLUMN raw_json TEXT')
        con.execute("UPDATE accruals SET raw_json='broken'")
        with pytest.raises(ValueError):rows(con)
    finally:con.close()

def test_required_amount_column_is_not_silently_zeroed():
    con=sqlite3.connect(':memory:')
    try:
        con.execute('CREATE TABLE accruals(date TEXT,sku INTEGER)')
        with pytest.raises(ValueError,match='missing required columns'):rows(con)
    finally:con.close()
