import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch
from unitka import load_transactions as loader


class TransactionLoaderSafetyTests(unittest.TestCase):
    def test_empty_accrual_day(self):
        client = Mock()
        client._post.return_value = {"accruals": []}
        self.assertEqual(loader._fetch_accrual_day(client, "2026-11-14"), [])

    def test_incomplete_accrual_day_raises(self):
        client = Mock()
        client._post.side_effect = [{"accruals": [{}], "last_id": "a"}, None]
        with self.assertRaises(RuntimeError):
            loader._fetch_accrual_day(client, "2026-11-14")

    def test_repeated_accrual_cursor(self):
        client = Mock()
        client._post.return_value = {"accruals": [{}], "last_id": "a"}
        with self.assertRaisesRegex(RuntimeError, "Repeated"):
            loader._fetch_accrual_day(client, "2026-11-14")

    def test_reversed_dates_do_not_connect(self):
        with patch.object(loader, "connect") as connect:
            with self.assertRaises(ValueError):
                loader.load_accruals(Mock(), "2026-11-15", "2026-11-14")
        connect.assert_not_called()

    def database(self, path):
        with closing(sqlite3.connect(path)) as conn:
            conn.executescript("""
                CREATE TABLE finance_transactions (operation_id TEXT PRIMARY KEY, date TEXT,
                    type TEXT, operation_type TEXT, amount REAL, posting_number TEXT,
                    sku TEXT, raw_json TEXT, fetched_at TEXT);
                CREATE TABLE balance_periods (period_begin TEXT, period_end TEXT,
                    orders_amount REAL, returns_amount REAL, commission_amount REAL,
                    services_amount REAL, delivery_amount REAL, raw_json TEXT,
                    begin_balance REAL, end_balance REAL, payments_total REAL,
                    UNIQUE(period_begin, period_end));
                CREATE TABLE finance_payouts (payout_id TEXT PRIMARY KEY, date TEXT,
                    amount REAL, period_from TEXT, period_to TEXT, status TEXT,
                    raw_json TEXT, fetched_at TEXT);
            """)

    def test_accrual_failure_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.db"
            self.database(db)
            conn = sqlite3.connect(db)
            client = Mock()
            client._post.side_effect = [
                {"accruals": [{"accrual_id": "1", "date": "2026-11-14", "total_amount": {"amount": 10}}]}, None]
            try:
                with patch.object(loader, "connect", return_value=conn), patch("builtins.print"):
                    with self.assertRaises(RuntimeError):
                        loader.load_accruals(client, "2026-11-14", "2026-11-15")
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")
            finally:
                conn.close()
            with closing(sqlite3.connect(db)) as check:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM finance_transactions").fetchone()[0], 0)

    def test_payout_second_page_failure_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.db"
            self.database(db)
            conn = sqlite3.connect(db)
            client = Mock()
            client._post.side_effect = [{"result": {"page_count": 2,
                "cash_flows": [{"period": {"begin": "2026-11-01", "end": "2026-11-14"}}],
                "details": []}}, None]
            try:
                with patch.object(loader, "connect", return_value=conn), patch("builtins.print"):
                    with self.assertRaises(RuntimeError):
                        loader.load_payouts(client, "2026-11-01", "2026-11-14")
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")
            finally:
                conn.close()
            with closing(sqlite3.connect(db)) as check:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM balance_periods").fetchone()[0], 0)

    def test_empty_payout_success(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.db"
            self.database(db)
            conn = sqlite3.connect(db)
            client = Mock()
            client._post.return_value = {"result": {"page_count": 1, "cash_flows": [], "details": []}}
            try:
                with patch.object(loader, "connect", return_value=conn), patch("builtins.print"):
                    self.assertEqual(loader.load_payouts(client, "2026-11-01", "2026-11-14"), 0)
            finally:
                conn.close()
