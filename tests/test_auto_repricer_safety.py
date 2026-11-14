"""Offline tests: no Ozon credentials or network calls."""
import ast
import contextlib
import io
import math
import unittest
from unitka import auto_repricer as r


class RepricerSafetyTests(unittest.TestCase):
    def test_apply_blocked_before_dependencies(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            r.main(["--apply"])
        self.assertEqual(raised.exception.code, 2)

    def test_modes_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            r.main(["--apply", "--dry-run"])

    def test_negative_limit_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            r.main(["--limit", "-1"])

    def test_invalid_numbers(self):
        for value in (None, "", "bad", -1, 0, float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertIsNone(r._positive(value))

    def test_positive_number(self):
        self.assertEqual(r._positive("12.5"), 12.5)

    def test_preview_step_remains_below_floor(self):
        task = r.build_tasks({1: {"min_direct": 200}}, {1: "A"}, {"A": 100})[0]
        self.assertEqual(task["new"], 115)
        self.assertTrue(task["still_below_floor"])

    def test_preview_reaches_floor(self):
        task = r.build_tasks({1: {"min_direct": 105}}, {1: "A"}, {"A": 100})[0]
        self.assertEqual(task["new"], 107.1)
        self.assertFalse(task["still_below_floor"])

    def test_skip_no_price_or_floor(self):
        self.assertEqual(r.build_tasks({1: {"min_direct": None}}, {1: "A"}, {"A": 100}), [])
        self.assertEqual(r.build_tasks({1: {"min_direct": 200}}, {1: "A"}, {}), [])

    def test_skip_price_above_floor(self):
        self.assertEqual(r.build_tasks({1: {"min_direct": 90}}, {1: "A"}, {"A": 100}), [])

    def test_duplicate_offer_skipped(self):
        self.assertEqual(r.build_tasks({1: {"min_direct": 200}}, {1: "A", 2: "A"}, {"A": 100}), [])

    def test_deterministic_limit(self):
        result = r.build_tasks({1: {"min_direct": 200}, 2: {"min_direct": 200}},
                               {1: "B", 2: "A"}, {"A": 100, "B": 100}, 1)
        self.assertEqual(result[0]["offer_id"], "A")

    def test_api_failure_propagates(self):
        class Client:
            def _post(self, *args):
                raise RuntimeError("offline")
        with self.assertRaises(RuntimeError):
            r.get_real_prices(Client(), ["A"])

    def test_response_validation(self):
        class Client:
            def __init__(self, response): self.response = response
            def _post(self, *args): return self.response
        for response in ({}, {"items": [], "has_next": True}, {"items": [], "cursor": "next"}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                r.get_real_prices(Client(response), ["A"])
        self.assertEqual(r.get_real_prices(Client({"items": [{"offer_id": "A", "price": {"price": "100"}}]}), ["A"]), {"A": 100})

    def test_no_write_api_calls_in_module(self):
        import inspect
        tree = ast.parse(inspect.getsource(r))
        forbidden = {"update_prices", "commit", "executemany", "executescript"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden)


if __name__ == "__main__":
    unittest.main()
