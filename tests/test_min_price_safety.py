"""Offline minimum-price writer interlock tests; no credentials or HTTP."""
import ast
import contextlib
import io
import unittest
from unittest.mock import patch
from unitka import update_min_prices as m


class MinPriceSafetyTests(unittest.TestCase):
    def test_apply_blocked_before_preview(self):
        with patch.object(m,"_preview") as preview,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            m.main(["--apply"])
        self.assertEqual(error.exception.code,2);preview.assert_not_called()

    def test_default_is_preview(self):
        with patch.object(m,"_preview",return_value=0) as preview:
            self.assertEqual(m.main([]),0)
        preview.assert_called_once_with(10)

    def test_dry_run_is_preview(self):
        with patch.object(m,"_preview",return_value=0) as preview:
            self.assertEqual(m.main(["--dry-run","--limit","0"]),0)
        preview.assert_called_once_with(0)

    def test_modes_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            m.main(["--apply","--dry-run"])

    def test_negative_limit_blocked(self):
        with patch.object(m,"_preview") as preview,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            m.main(["--limit","-1"])
        preview.assert_not_called()

    def test_valid_candidate(self):
        tasks=m.build_tasks({1:{"min_direct":100}},{1:"A"},{"A":120})
        self.assertEqual(tasks,[dict(offer_id="A",min_price=100,current_price=120)])

    def test_below_floor_not_proposed_for_protection(self):
        self.assertEqual(m.build_tasks({1:{"min_direct":150}},{1:"A"},{"A":100}),[])

    def test_unknown_or_invalid_floor_omitted(self):
        for value in (None,0,-1,True,float("nan"),float("inf"),"bad"):
            with self.subTest(value=value):
                self.assertEqual(m.build_tasks({1:{"min_direct":value}},{1:"A"},{"A":100}),[])

    def test_unknown_or_invalid_price_omitted(self):
        for value in (None,0,-1,True,float("nan"),float("inf"),"bad"):
            with self.subTest(value=value):
                self.assertEqual(m.build_tasks({1:{"min_direct":50}},{1:"A"},{"A":value}),[])

    def test_duplicate_offer_omitted(self):
        self.assertEqual(m.build_tasks({1:{"min_direct":50},2:{"min_direct":50}},{1:"A",2:"A"},{"A":100}),[])

    def test_missing_mapping_omitted(self):
        self.assertEqual(m.build_tasks({1:{"min_direct":50}},{},{"A":100}),[])

    def test_no_api_write_or_db_commit_calls(self):
        import inspect
        source=inspect.getsource(m)
        forbidden={"update_prices","commit","executemany","executescript"}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,forbidden)
        self.assertNotIn("/v1/product/import/prices",source)
        self.assertNotIn("min_price_for_auto_actions_enabled",source)

    def test_preview_errors_not_reported_as_success(self):
        with patch.object(m,"_preview",side_effect=RuntimeError("offline")),self.assertRaises(RuntimeError):
            m.main([])


if __name__ == "__main__":
    unittest.main()
