import importlib.util
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_module():
    path = Path(__file__).resolve().parents[1] / "app" / "sync_finance.py"
    spec = importlib.util.spec_from_file_location("sync_finance_safety_test_target", path)
    module = importlib.util.module_from_spec(spec)
    with patch("dotenv.load_dotenv"):
        spec.loader.exec_module(module)
    return module


class SyncFinanceSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_http_error_raises(self):
        response = Mock(status_code=503)
        with patch.object(self.mod.requests, "post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                self.mod.post("/test", {})
        response.json.assert_not_called()

    def test_valid_empty_day(self):
        with patch.object(self.mod, "post", return_value={"accruals": []}):
            self.assertEqual(self.mod.fetch_day("2026-11-14"), [])

    def test_error_after_first_page_does_not_return_partial_day(self):
        with patch.object(self.mod, "post", side_effect=[
            {"accruals": [{"accrual_id": "1"}], "last_id": "a"}, RuntimeError("API failed")
        ]):
            with self.assertRaisesRegex(RuntimeError, "API failed"):
                self.mod.fetch_day("2026-11-14")

    def test_repeated_cursor_raises(self):
        page = {"accruals": [{"accrual_id": "1"}], "last_id": "a"}
        with patch.object(self.mod, "post", side_effect=[page, page]):
            with self.assertRaisesRegex(RuntimeError, "Repeated"):
                self.mod.fetch_day("2026-11-14")

    def test_malformed_response_raises(self):
        for data in ({}, None, {"accruals": None}, {"accruals": [None]}, {"accruals": [], "last_id": "a"}):
            with self.subTest(data=data), patch.object(self.mod, "post", return_value=data):
                with self.assertRaises(RuntimeError):
                    self.mod.fetch_day("2026-11-14")

    def test_pagination_limit_raises(self):
        pages = [{"accruals": [{}], "last_id": str(i)} for i in range(200)]
        with patch.object(self.mod, "post", side_effect=pages):
            with self.assertRaisesRegex(RuntimeError, "limit"):
                self.mod.fetch_day("2026-11-14")

    def test_main_rolls_back_prior_day_and_closes_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.db"
            with closing(sqlite3.connect(db)) as setup:
                setup.execute("CREATE TABLE marker (id TEXT)")
            actual = sqlite3.connect(db)
            def save(cur, acc, types):
                cur.execute("INSERT INTO marker VALUES (?)", (acc["accrual_id"],))
                return 1, 0
            with patch.object(self.mod, "DB", str(db)), \
                 patch.object(self.mod.sqlite3, "connect", return_value=actual), \
                 patch.object(self.mod, "parse_args", return_value={"date_from": "2026-11-14", "date_to": "2026-11-15"}), \
                 patch.object(self.mod, "get_types", return_value={}), \
                 patch.object(self.mod, "save_accrual", side_effect=save), \
                 patch.object(self.mod, "fetch_day", side_effect=[[{"accrual_id": "1", "date":"2026-11-14", "total_amount":{"amount":10}}], RuntimeError("day failed")]), \
                 patch("builtins.print"):
                with self.assertRaisesRegex(RuntimeError, "day failed"):
                    self.mod.main()
            with self.assertRaises(sqlite3.ProgrammingError):
                actual.execute("SELECT 1")
            with closing(sqlite3.connect(db)) as check:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM marker").fetchone()[0], 0)
