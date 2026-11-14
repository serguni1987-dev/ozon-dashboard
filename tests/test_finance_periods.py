"""Regression tests of complete ozon_pnl; SQLite fixtures, no external services."""
import json
import sqlite3
import unittest
from unitka.finance_core import ozon_pnl, _month_bounds


class FinancePeriodTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE accruals(date TEXT,sku INTEGER,accrued_category TEXT,
                sale_price REAL,bonus REAL,coinvestment REAL,sale_commission REAL);
            CREATE TABLE finance_transactions(date TEXT,type TEXT,amount REAL);
            CREATE TABLE monthly_reports(month TEXT,sale_price_sum REAL,bonus_sum REAL,
                coinvestment_sum REAL,gross_commission_sum REAL);
            CREATE TABLE monthly_realization_rows(month TEXT,sku INTEGER,quantity REAL,raw_json TEXT);
            CREATE TABLE product_cost_history(sku INTEGER,date_from TEXT,cost_price REAL);
            INSERT INTO product_cost_history VALUES(1,'2026-01-01',100);
            INSERT INTO monthly_reports VALUES('2026-10',9000,500,100,1000);
        """)
        for day, amount in [('2026-09-28',1000), ('2026-10-01',1000),
                            ('2026-10-10',1000), ('2026-10-15',1000),
                            ('2026-10-20',-1000), ('2026-10-31',1000),
                            ('2026-11-01',1000)]:
            self.db.execute("INSERT INTO accruals VALUES(?,1,'POSTING',?,0,0,?)",
                            (day,amount,-amount/10))
            self.db.execute("INSERT INTO finance_transactions VALUES(?,'income',?)",
                            (day,amount*0.9))
        raw = json.dumps({'delivery_commission':{'quantity':10},'return_commission':{'quantity':2}})
        self.db.execute("INSERT INTO monthly_realization_rows VALUES('2026-10',1,10,?)",(raw,))
        self.db.commit()

    def pnl(self, start, end):
        return ozon_pnl(self.db.cursor(),start,end)

    def test_full_month_uses_monthly_net_quantity(self):
        result = self.pnl('2026-10-01','2026-11-01')
        self.assertEqual(result['cogs'],800)
        self.assertEqual(result['income'],9600)
        self.assertFalse(result['cogs_estimated'])

    def test_partial_start_does_not_take_whole_month(self):
        result = self.pnl('2026-10-15','2026-11-01')
        self.assertEqual(result['cogs'],100)
        self.assertEqual(result['income'],1000)
        self.assertTrue(result['cogs_estimated'])

    def test_partial_end(self):
        self.assertEqual(self.pnl('2026-10-01','2026-10-15')['cogs'],200)

    def test_both_partial(self):
        self.assertEqual(self.pnl('2026-10-10','2026-10-21')['cogs'],100)

    def test_end_is_exclusive(self):
        self.assertEqual(self.pnl('2026-10-15','2026-10-20')['cogs'],100)

    def test_return_only_daily(self):
        self.assertEqual(self.pnl('2026-10-20','2026-10-21')['cogs'],-100)

    def test_return_only_monthly(self):
        raw = json.dumps({'return_commission':{'quantity':2}})
        self.db.execute('UPDATE monthly_realization_rows SET quantity=0,raw_json=?',(raw,))
        self.assertEqual(self.pnl('2026-10-01','2026-11-01')['cogs'],-200)

    def test_missing_monthly_quantity_falls_back(self):
        self.db.execute("UPDATE monthly_realization_rows SET quantity=3,raw_json='{}'")
        self.assertEqual(self.pnl('2026-10-01','2026-11-01')['cogs'],300)

    def test_missing_report_uses_daily(self):
        self.db.execute('DELETE FROM monthly_realization_rows')
        result = self.pnl('2026-10-01','2026-11-01')
        self.assertEqual(result['cogs'],300)
        self.assertTrue(result['cogs_estimated'])

    def test_partial_edges_full_middle(self):
        self.assertEqual(self.pnl('2026-09-15','2026-11-02')['cogs'],1000)

    def test_partial_first_month_plus_open_next(self):
        self.assertEqual(self.pnl('2026-10-15','2026-11-02')['cogs'],200)

    def test_empty_interval(self):
        result = self.pnl('2026-10-15','2026-10-15')
        self.assertEqual(result['cogs'],0)
        self.assertEqual(result['income'],0)

    def test_full_year(self):
        self.assertEqual(self.pnl('2026-01-01','2027-01-01')['cogs'],1000)

    def test_profit_identity(self):
        result = self.pnl('2026-10-15','2026-11-01')
        self.assertEqual(result['gross_profit'], result['net_from_ozon']-result['cogs'])

    def test_read_only_connection(self):
        self.db.execute('PRAGMA query_only=ON')
        self.assertEqual(self.pnl('2026-10-15','2026-11-01')['cogs'],100)

    def test_year_boundary_month_selection(self):
        self.assertEqual(_month_bounds('2026-12-15','2027-02-01'),
                         [('2027-01','2027-01-01','2027-02-01')])

    def test_no_data(self):
        self.assertEqual(self.pnl('2025-01-01','2025-02-01')['cogs'],0)


if __name__ == '__main__':
    unittest.main()
