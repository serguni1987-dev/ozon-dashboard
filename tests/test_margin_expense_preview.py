"""Offline tests for isolated expense-only SKU candidate."""
import copy
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unitka import margin_expense_preview as m

GROUPS = {"logistics":{17,29,32,45,59},"agents":{1,74}}


class MarginExpensePreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"test.db"
        with closing(sqlite3.connect(self.path)) as con:
            con.executescript("""
                CREATE TABLE accrual_sku_daily(date TEXT, sku INTEGER, type_id INTEGER, amount REAL);
                CREATE TABLE products(sku INTEGER, offer_id TEXT, name TEXT, category_l1 TEXT);
                INSERT INTO products VALUES(2,'TWO','Product','Category');
            """)
            con.commit()
        self.con = sqlite3.connect(self.path.as_uri()+"?mode=ro", uri=True)
        self.addCleanup(self.con.close)
        self.con.execute("PRAGMA query_only=ON")

    def fees(self, rows):
        with closing(sqlite3.connect(self.path)) as con:
            con.executemany("INSERT INTO accrual_sku_daily VALUES(?,?,?,?)", rows)
            con.commit()

    def candidate(self, data=None):
        return m.add_missing_expense_skus(self.con, data or {}, "2026-10-01", "2026-10-31", GROUPS)

    def test_october_expense_only_reproduced(self):
        self.fees([('2026-10-02',2,29,-8.09),('2026-10-02',2,45,-15),
            ('2026-10-02',2,32,-148),('2026-10-02',2,59,-148),
            ('2026-10-02',2,17,-10),('2026-10-18',2,32,-209),('2026-10-18',2,59,-167)])
        data, added = self.candidate()
        self.assertEqual(added,[2])
        self.assertAlmostEqual(data[2]['logistics'],705.09)
        self.assertEqual(data[2]['purchased'],0)
        self.assertEqual(data[2]['cogs'],0)
        self.assertEqual(data[2]['offer_id'],'TWO')
        report=m.profit_preview(data,705.09)
        self.assertTrue(report['rows'][0]['included'])
        self.assertAlmostEqual(report['displayed_profit_before_tax'],-705.09)

    def test_existing_rows_not_recalculated_or_mutated(self):
        self.fees([('2026-10-02',1,32,-20),('2026-10-02',2,32,-10)])
        source={1:dict(sku=1,revenue=1000,commission=100,logistics=20,cogs=400)}
        original=copy.deepcopy(source)
        result,added=self.candidate(source)
        self.assertEqual(source,original)
        self.assertEqual(result[1],source[1])
        self.assertEqual(added,[2])

    def test_store_profit_unchanged_and_residual_reduced(self):
        self.fees([('2026-10-02',2,32,-705.09)])
        source={1:dict(sku=1,revenue=2000,commission=100,cogs=400,purchased=1)}
        candidate,_=self.candidate(source)
        before=m.profit_preview(source,1000)
        after=m.profit_preview(candidate,1000)
        self.assertAlmostEqual(before['profit_before_tax'],after['profit_before_tax'])
        self.assertAlmostEqual(before['unallocated']-after['unallocated'],705.09)
        self.assertAlmostEqual(after['rows'][0]['profit_before_tax']-before['rows'][0]['profit_before_tax'],705.09)

    def test_period_and_zero_groups(self):
        self.fees([('2026-09-30',2,32,-50),('2026-11-01',3,32,-60),('2026-10-02',4,32,0)])
        self.assertEqual(self.candidate(),({},[]))

    def test_unassigned_services_not_turned_into_sku(self):
        self.fees([('2026-10-02',None,32,-10),('2026-10-02',0,32,-20)])
        self.assertEqual(self.candidate(),({},[]))

    def test_unknown_service_and_legacy_sign_preserved(self):
        self.fees([('2026-10-02',2,999,-10),('2026-10-02',3,1,5)])
        result,_=self.candidate()
        self.assertEqual(result[2]['other'],10)
        self.assertEqual(result[3]['agents'],5)

    def test_readonly_database_unchanged(self):
        self.fees([('2026-10-02',2,32,-10)])
        before=hashlib.sha256(self.path.read_bytes()).digest()
        self.candidate()
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).digest())
        with self.assertRaises(sqlite3.OperationalError):
            self.con.execute("DELETE FROM products")

    def test_duplicate_keys_and_nonfinite_block(self):
        with self.assertRaises(ValueError):
            self.candidate({1:{},'1':{}})
        self.fees([('2026-10-02',2,32,float('inf'))])
        with self.assertRaises(ValueError):
            self.candidate()


if __name__ == '__main__':
    unittest.main()
