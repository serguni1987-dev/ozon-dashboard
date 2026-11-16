import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import Mock, patch
from unitka import load_transactions as loader


class BalancePeriodMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript("""
                CREATE TABLE balance_periods (
                    period_begin TEXT, period_end TEXT, begin_balance REAL,
                    end_balance REAL, payments_total REAL, orders_amount REAL,
                    returns_amount REAL, commission_amount REAL, services_amount REAL,
                    delivery_amount REAL, raw_json TEXT,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(period_begin, period_end));
                CREATE TABLE finance_payouts (
                    payout_id TEXT PRIMARY KEY, date TEXT, amount REAL,
                    period_from TEXT, period_to TEXT, status TEXT,
                    raw_json TEXT, fetched_at TEXT);
            """)
        self.period = {'begin': '2026-11-01', 'end': '2026-11-14'}
        self.summary = dict(period=self.period, orders_amount=100,
            returns_amount=5, commission_amount=10, services_amount=3,
            item_delivery_and_return_amount=2)
        self.detail = dict(period=self.period, begin_balance_amount=20,
            end_balance_amount=90, payments=[{'payment': -10}])

    def run_load(self, summaries, details, fail=False):
        client = Mock()
        response = {'result': {'page_count': 2 if fail else 1,
            'cash_flows': summaries, 'details': details}}
        client._post.side_effect = [response, None] if fail else [response]
        with patch.object(loader, 'connect', side_effect=lambda: sqlite3.connect(self.path)), patch('builtins.print'):
            return loader.load_payouts(client, '2026-11-01', '2026-11-14')

    def row(self):
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute('SELECT orders_amount, returns_amount, commission_amount, services_amount, delivery_amount, begin_balance, end_balance, payments_total FROM balance_periods').fetchone()

    def test_both_sections_keep_all_amounts(self):
        self.run_load([self.summary], [self.detail])
        self.assertEqual(self.row(), (100, 5, 10, 3, 2, 20, 90, 10))

    def test_summary_refresh_preserves_existing_balances(self):
        self.run_load([], [self.detail])
        self.run_load([self.summary], [])
        self.assertEqual(self.row(), (100, 5, 10, 3, 2, 20, 90, 10))

    def test_details_refresh_preserves_existing_summary(self):
        self.run_load([self.summary], [])
        self.run_load([], [self.detail])
        self.assertEqual(self.row(), (100, 5, 10, 3, 2, 20, 90, 10))

    def test_repeat_updates_values_without_duplicate_periods(self):
        self.run_load([self.summary], [self.detail])
        self.summary['orders_amount'] = 200
        self.detail['end_balance_amount'] = 190
        self.run_load([self.summary], [self.detail])
        self.assertEqual(self.row(), (200, 5, 10, 3, 2, 20, 190, 10))
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM balance_periods').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM finance_payouts').fetchone()[0], 1)

    def test_failure_restores_existing_row(self):
        self.run_load([self.summary], [self.detail])
        previous = self.row()
        self.summary['orders_amount'] = 999
        self.detail['end_balance_amount'] = 999
        with self.assertRaises(RuntimeError):
            self.run_load([self.summary], [self.detail], fail=True)
        self.assertEqual(self.row(), previous)
