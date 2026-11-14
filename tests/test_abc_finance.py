"""Contract and CLI safety tests; no Google or Ozon access."""
import contextlib
import copy
import io
import json
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from unitka import abc_finance as a


def fixture():
    s = dict(income=1000,units=2,commission=100,svc_fixed=50,svc_pct=10,
             overhead=40,cogs=400,profit=400,delivered=2,returned=0,cost_unit=200)
    t = dict(income=1000,cogs=400,gross_profit=400,pnl_income=1000,
             pnl_cogs=400,pnl_gross_profit=400,cogs_estimated=False)
    return dict(skus={1:s},totals=t)


def retotal(eco):
    rows = eco["skus"].values()
    for field, target in (("income","pnl_income"),("cogs","pnl_cogs"),("profit","pnl_gross_profit")):
        value = sum(s[field] for s in rows)
        eco["totals"][target] = value
        eco["totals"]["gross_profit" if field=="profit" else field] = value
    return eco


class AbcFinanceTests(unittest.TestCase):
    def test_standard_expenses_subtract(self):
        self.assertEqual(a.prepare_rows(fixture())[0]["profit"],400)

    def test_service_refund_increases_profit(self):
        eco = fixture(); eco["skus"][1].update(svc_fixed=-50,profit=500)
        self.assertEqual(a.prepare_rows(retotal(eco))[0]["profit"],500)

    def test_return_only(self):
        eco = fixture(); eco["skus"][1].update(income=-500,units=-1,commission=-50,
            svc_fixed=0,svc_pct=0,overhead=0,cogs=-200,profit=-250,delivered=0,returned=1)
        self.assertEqual(a.prepare_rows(retotal(eco))[0]["profit"],-250)

    def test_expense_only_sku_retained(self):
        eco = fixture(); eco["skus"][2] = dict(income=0,units=0,commission=0,
            svc_fixed=50,svc_pct=0,overhead=0,cogs=0,profit=-50,delivered=0,returned=0,cost_unit=0)
        self.assertEqual(len(a.prepare_rows(retotal(eco))),2)

    def test_stock_only_sku_excluded(self):
        eco = fixture(); eco["skus"][2] = {k:0 for k in eco["skus"][1]}
        eco["skus"][2]["cost_unit"] = 300
        self.assertEqual(len(a.prepare_rows(eco)),1)

    def test_missing_cost_blocks(self):
        eco = fixture(); eco["skus"][1]["cost_unit"] = 0
        with self.assertRaisesRegex(ValueError,"cost"):
            a.prepare_rows(eco)

    def test_missing_cost_even_if_net_zero(self):
        eco = fixture(); eco["skus"][1].update(units=0,delivered=1,returned=1,cost_unit=0)
        with self.assertRaisesRegex(ValueError,"cost"):
            a.prepare_rows(eco)

    def test_nonfinite_blocks(self):
        for value in (float("nan"),float("inf"),None,"bad"):
            eco = fixture(); eco["skus"][1]["income"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.prepare_rows(eco)

    def test_each_reconciliation_blocks(self):
        for key in ("pnl_income","pnl_cogs","pnl_gross_profit","income","cogs","gross_profit"):
            eco = fixture(); eco["totals"][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                a.prepare_rows(eco)

    def test_row_profit_mismatch_blocks(self):
        eco = fixture(); eco["skus"][1]["profit"] += 1
        with self.assertRaises(ValueError): a.prepare_rows(eco)

    def test_invalid_sku_blocks(self):
        for sku in (None,0,-1,"bad",1.5):
            eco = fixture(); eco["skus"] = {sku:eco["skus"][1]}
            with self.subTest(sku=sku), self.assertRaises(ValueError): a.prepare_rows(eco)

    def test_duplicate_sku_blocks(self):
        eco = fixture(); eco["skus"]["1"] = copy.deepcopy(eco["skus"][1])
        with self.assertRaisesRegex(ValueError,"Duplicate"): a.prepare_rows(eco)

    def test_input_not_mutated(self):
        eco = fixture(); before = copy.deepcopy(eco)
        a.prepare_rows(eco)
        self.assertEqual(eco,before)

    def test_inclusive_end_converted_once(self):
        fake = types.ModuleType("unitka.unit_core")
        calls = []
        def engine(cur,start,stop):
            calls.append((start,stop));return fixture()
        fake.sku_economics = engine
        with sqlite3.connect(":memory:") as conn, patch.dict("sys.modules",{"unitka.unit_core":fake}):
            result = a.build_preview(conn,"2026-10-01","2026-10-31")
        self.assertEqual(calls,[("2026-10-01","2026-11-01")])
        self.assertEqual(result["sku_count"],1)

    def test_reversed_dates_block(self):
        with self.assertRaises(ValueError): a.build_preview(None,"2026-11-01","2026-10-01")

    def test_missing_db_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/"missing.db"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                a.main(["--db",str(source),"--from","2026-10-01","--to","2026-10-31","--out",str(Path(folder)/"out.csv")])
            self.assertFalse(source.exists())

    def test_cli_opens_readonly_and_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/"source.db"; target = Path(folder)/"out.csv"
            conn = sqlite3.connect(source);conn.execute("CREATE TABLE test(value)");conn.commit();conn.close()
            before = source.read_bytes()
            def preview(conn,*args):
                with self.assertRaises(sqlite3.OperationalError): conn.execute("INSERT INTO test VALUES(1)")
                return dict(rows=a.prepare_rows(fixture()),profit=400)
            with patch.object(a,"build_preview",side_effect=preview), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(a.main(["--db",str(source),"--from","2026-10-01","--to","2026-10-31","--out",str(target)]),0)
            self.assertEqual(source.read_bytes(),before)
            self.assertIn("profit",target.read_text(encoding="utf-8-sig"))

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/"source.db"; source.write_bytes(b"test")
            target = Path(folder)/"out.csv"; target.write_text("KEEP")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                a.main(["--db",str(source),"--from","2026-10-01","--to","2026-10-31","--out",str(target)])
            self.assertEqual(target.read_text(),"KEEP")


if __name__ == "__main__":
    unittest.main()
