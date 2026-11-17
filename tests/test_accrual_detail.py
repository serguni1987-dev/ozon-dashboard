"""Offline regressions: run python -m pytest tests/test_accrual_detail.py -q."""
import copy
import json
import sqlite3
import pytest
from unitka.accrual_detail import product_rows, iter_accrual_products, save_accrual_record

SCHEMA = """
CREATE TABLE accruals(accrual_id INTEGER PRIMARY KEY,date TEXT,sku INTEGER,unit_number TEXT,
accrued_category TEXT,delivery_schema TEXT,seller_price REAL,sale_price REAL,
sale_commission REAL,bonus REAL,coinvestment REAL,total_amount REAL,raw_json TEXT);
CREATE TABLE accruals_services(id INTEGER PRIMARY KEY,accrual_id INTEGER REFERENCES accruals(accrual_id),
date TEXT,sku INTEGER,type_id INTEGER,type_name TEXT,amount REAL);
"""

def db():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    return c

def sample():
    return {"accrual_id": 10, "date": "2026-01-27", "accrued_category": "POSTING",
        "total_amount": {"amount": "115"}, "posting": {"products": [
            {"sku": 101, "quantity": 2, "commission": {"seller_price": {"amount": "100"},
             "sale_price": {"amount": "80"}, "bonus": {"amount": "20"},
             "sale_commission": {"amount": "-30"}},
             "delivery": {"services": [{"type_id": 32, "accrued": {"amount": "-5"}}]}},
            {"sku": 102, "quantity": 1, "commission": {"seller_price": {"amount": "70"},
             "sale_price": {"amount": "60"}, "bonus": {"amount": "10"},
             "sale_commission": {"amount": "-20"}}}]}}

def read(c):
    return list(iter_accrual_products(c.cursor(), "2026-01-01", "2026-02-01"))

def test_header_keeps_net_once_and_all_income():
    c = db(); save_accrual_record(c.cursor(), sample(), {})
    assert c.execute("SELECT count(*),sum(total_amount),sum(sale_price+bonus) FROM accruals").fetchone() == (1, 115, 170)
    assert c.execute("SELECT sku FROM accruals").fetchone()[0] is None

def test_two_skus_and_actual_quantity():
    c = db(); save_accrual_record(c.cursor(), sample(), {})
    assert [(r["sku"],r["quantity"]) for r in read(c)] == [(101,2),(102,1)]

def test_amounts_are_not_multiplied_by_quantity():
    assert product_rows(sample())[0]["sale_price"] == 80

def test_repeated_save_does_not_duplicate_services():
    c = db()
    for _ in range(3): save_accrual_record(c.cursor(), sample(), {})
    assert c.execute("SELECT count(*),sum(amount) FROM accruals_services").fetchone() == (1,-5)

def test_changed_services_replace_old_values():
    c = db(); a=sample(); save_accrual_record(c.cursor(), a, {})
    a["posting"]["products"][0]["delivery"]["services"][0]["accrued"]["amount"]="-9"
    save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT count(*),sum(amount) FROM accruals_services").fetchone()==(1,-9)

def test_removed_services_disappear():
    c=db();a=sample();save_accrual_record(c.cursor(),a,{})
    a["posting"]["products"][0]["delivery"]={}
    save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT count(*) FROM accruals_services").fetchone()[0]==0

def test_no_implicit_commit_and_outer_rollback():
    c=db();save_accrual_record(c.cursor(),sample(),{})
    assert c.in_transaction
    c.rollback()
    assert c.execute("SELECT count(*) FROM accruals").fetchone()[0]==0

def test_save_failure_restores_previous_header_and_services():
    c=db();a=sample();save_accrual_record(c.cursor(),a,{});c.commit()
    c.execute("CREATE TRIGGER reject_service BEFORE INSERT ON accruals_services BEGIN SELECT RAISE(ABORT,'injected'); END")
    a["total_amount"]={"amount":"999"}
    with pytest.raises(sqlite3.IntegrityError):save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT total_amount FROM accruals").fetchone()[0]==115
    assert c.execute("SELECT sum(amount) FROM accruals_services").fetchone()[0]==-5

def test_old_last_product_columns_do_not_override_json():
    c=db();save_accrual_record(c.cursor(),sample(),{})
    c.execute("UPDATE accruals SET sku=102,sale_price=60,bonus=10")
    assert sum(r["sale_price"]+r["bonus"] for r in read(c))==170

def test_return_preserves_signed_quantity_and_commission():
    a=sample();p=a["posting"]["products"][0]
    p["commission"]["sale_price"]={"amount":"-80"}
    p["commission"]["sale_commission"]={"amount":"30"}
    row=product_rows(a)[0]
    assert row["sale_price"]==-80 and row["quantity"]==2 and row["sale_commission"]==30

def test_zero_commission_does_not_use_fallback():
    a=sample();comm=a["posting"]["products"][0]["commission"]
    comm["sale_commission"]={"amount":"0"};comm["commission"]={"amount":"-99"}
    assert product_rows(a)[0]["sale_commission"]==0

def test_commission_fallback_when_missing():
    a=sample();comm=a["posting"]["products"][0]["commission"]
    del comm["sale_commission"];comm["commission"]={"amount":"-12"}
    assert product_rows(a)[0]["sale_commission"]==-12

def test_same_sku_multiple_products_remain_separate():
    a=sample();a["posting"]["products"][1]["sku"]=101
    c=db();save_accrual_record(c.cursor(),a,{})
    assert len(read(c))==2 and sum(r["quantity"] for r in read(c))==3

def test_orphan_operation_preserved():
    c=db();a={"accrual_id":9,"date":"2026-01-01","accrued_category":"FINE","total_amount":{"amount":"-7"}}
    save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT type_id,amount FROM accruals_services").fetchone()==(0,-7)

def test_legacy_no_json_fallback():
    c=db();c.execute("INSERT INTO accruals(accrual_id,date,sku,sale_price,raw_json) VALUES (1,'2026-01-01',101,55,NULL)")
    assert read(c)[0]["sale_price"]==55 and read(c)[0]["quantity"]==1

def test_invalid_json_fails_instead_of_hiding_error():
    c=db();c.execute("INSERT INTO accruals(accrual_id,date,raw_json) VALUES (1,'2026-01-01','broken')")
    with pytest.raises(ValueError):read(c)

@pytest.mark.parametrize("bad",["NaN","Infinity","-Infinity",True,"not-money"])
def test_bad_money_rejected_before_write(bad):
    c=db();a=sample();a["posting"]["products"][0]["commission"]["sale_price"]={"amount":bad}
    with pytest.raises((ValueError,TypeError)):save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT count(*) FROM accruals").fetchone()[0]==0

@pytest.mark.parametrize("bad",[0,-1,1.5,None])
def test_invalid_quantity_rejected(bad):
    a=sample();a["posting"]["products"][0]["quantity"]=bad
    with pytest.raises(ValueError):product_rows(a)

def test_half_open_date_range():
    c=db();save_accrual_record(c.cursor(),sample(),{})
    assert list(iter_accrual_products(c.cursor(),'2026-01-01','2026-01-27'))==[]

def test_service_only_product_has_no_sales():
    a=sample();a["posting"]["products"][0]["commission"]=None
    row=product_rows(a)[0]
    assert row["sale_price"]==0 and row["sale_commission"]==0

def test_different_operations_with_same_payload_not_merged():
    c=db();a=sample();save_accrual_record(c.cursor(),a,{})
    a["accrual_id"]=11;save_accrual_record(c.cursor(),a,{})
    assert c.execute("SELECT count(*),sum(total_amount) FROM accruals").fetchone()==(2,230)
