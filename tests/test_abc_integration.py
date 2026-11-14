"""ABC integration contract and preview-safety regression tests, offline."""
import contextlib
import io
import json
import sqlite3
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from unitka import calc_abc_xyz as a


def preview():
    return dict(rows=[dict(sku=1,income=1000,units=2,profit=400),
                      dict(sku=2,income=0,units=0,profit=-500)],
                income=1000,profit=-100,cogs_estimated=True)


class AbcIntegrationTests(unittest.TestCase):
    def compute(self, active=None):
        with patch.object(a,"build_preview",return_value=preview()), \
             patch.object(a,"_load_active_months",return_value=active or {}), \
             patch.object(a,"_load_capital",return_value=({},False)):
            return a.compute_from_connection(None,"2026-02-17","2026-11-13")

    def test_top_item_is_a_even_above_95_percent(self):
        self.assertEqual(a._classify_abc([(1,99),(2,1)])[1][0],"A")

    def test_single_positive_item_is_a(self):
        self.assertEqual(a._classify_abc([(1,10)])[1],("A",100,100))

    def test_losses_and_zero_are_c(self):
        result = a._classify_abc([(1,100),(2,0),(3,-100)])
        self.assertEqual(result[2][0],"C");self.assertEqual(result[3][1],0)

    def test_all_losses_have_zero_contribution(self):
        self.assertEqual(a._classify_abc([(1,-10),(2,-20)]),{1:("C",0,0),2:("C",0,0)})

    def test_abc_sort_is_deterministic(self):
        self.assertEqual(a._classify_abc([(2,1),(1,1)]),a._classify_abc([(1,1),(2,1)]))

    def test_nonfinite_profit_blocks(self):
        with self.assertRaises(ValueError):a._classify_abc([(1,float("nan"))])

    def test_cv_includes_zero_months(self):
        self.assertEqual(a._cv([10,10]),0)
        self.assertGreater(a._cv([10,0,10]),25)

    def test_cv_invalid_quantity_blocks(self):
        for values in ([1,-1],[1,float("inf")]):
            with self.subTest(values=values),self.assertRaises(ValueError):a._cv(values)

    def test_xyz_not_enough_active_months(self):
        self.assertEqual(a._classify_xyz(0,2,3,25)[0],"N/A")

    def test_xyz_thresholds(self):
        self.assertEqual([a._classify_xyz(cv,3,3,25)[0] for cv in (10,25,26)],["X","Y","Z"])

    def test_net_profit_not_positive_base(self):
        data = self.compute()
        self.assertEqual(data["total_profit"],-100)
        self.assertEqual(data["positive_profit_base"],400)

    def test_expense_only_sku_retained(self):
        self.assertEqual(len(self.compute()["items"]),2)

    def test_loss_has_no_purchase_recommendation(self):
        data = self.compute({1:{"2026-03":1,"2026-04":1,"2026-05":1},
                             2:{"2026-03":1,"2026-04":1,"2026-05":1}})
        item = next(i for i in data["items"] if i["sku"]==2)
        self.assertEqual(item["abc"],"C")
        self.assertIn("не использовать",item["recommendation"])

    def test_active_count_ignores_zero_months(self):
        item = self.compute({1:{"2026-03":1,"2026-04":0,"2026-05":1}})["items"][0]
        self.assertEqual(item["active_months"],2)
        self.assertEqual(item["xyz"],"N/A")

    def test_missing_cost_or_reconciliation_error_propagates(self):
        with patch.object(a,"build_preview",side_effect=ValueError("Missing positive cost")):
            with self.assertRaises(ValueError):a.compute_from_connection(None,"2026-10-01","2026-10-31")

    def test_export_columns(self):
        for row in a._build_full_rows(self.compute()):
            self.assertEqual(len(row),len(a.HEADER_FULL))

    def test_compute_opens_readonly(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/"source.db"
            conn=sqlite3.connect(source);conn.execute("CREATE TABLE t(x)");conn.commit();conn.close()
            before=source.read_bytes()
            def check(conn,*args):
                with self.assertRaises(sqlite3.OperationalError):conn.execute("INSERT INTO t VALUES(1)")
                return {"ok":True}
            with patch.object(a,"compute_from_connection",side_effect=check):
                self.assertEqual(a._compute(date(2026,10,1),date(2026,10,31),{},source),{"ok":True})
            self.assertEqual(source.read_bytes(),before)

    def test_missing_db_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"absent.db"
            with self.assertRaises(ValueError):a._compute(date(2026,10,1),date(2026,10,31),{},source)
            self.assertFalse(source.exists())

    def test_publish_blocked_before_compute(self):
        with patch.object(a,"_compute") as compute, contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            a.main(["--publish"])
        compute.assert_not_called()

    def test_default_cli_only_exports_preview(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(a,"_compute",return_value=self.compute()),contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(a.main(["--from","2026-02-17","--to","2026-11-13","--out-dir",folder]),0)
            summary=json.loads(stdout.getvalue())
            self.assertTrue(summary["preview_only"])
            self.assertEqual(summary["total_profit"],-100)
            self.assertEqual(len(list(Path(folder).glob("*.csv"))),1)
            self.assertEqual(len(list(Path(folder).glob("*.json"))),1)

    def test_complete_months_only_for_xyz(self):
        finance=types.ModuleType("unitka.finance_core")
        finance._month_bounds=lambda start,stop:[("2026-10","2026-10-01","2026-11-01")]
        unit=types.ModuleType("unitka.unit_core");calls=[]
        def engine(cur,start,stop):
            calls.append((start,stop));return {"skus":{1:{"delivered":3},2:{"delivered":0}}}
        unit.sku_economics=engine
        conn=sqlite3.connect(":memory:")
        try:
            with patch.dict("sys.modules",{"unitka.finance_core":finance,"unitka.unit_core":unit}):
                result=a._load_active_months(conn,"2026-09-15","2026-11-13")
        finally:conn.close()
        self.assertEqual(calls,[("2026-10-01","2026-11-01")])
        self.assertEqual(result,{1:{"2026-10":3}})


if __name__ == "__main__":
    unittest.main()
