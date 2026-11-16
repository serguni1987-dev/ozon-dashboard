import unittest
from unittest.mock import Mock, patch
from unitka import calc_unit_summary as summary


def economics():
    return {"skus": {123: {"offer_id": "A", "income": 100.0,
        "cogs": 30.0, "commission": 10.0, "svc_fixed": 5.0,
        "svc_pct": 2.0, "overhead": 3.0, "profit": 50.0}}}


class SummaryIntegrationTests(unittest.TestCase):
    def test_mapping_and_inclusive_month_end(self):
        cur = Mock()
        with patch.object(summary, "sku_economics", return_value=economics()) as core:
            result = summary.build_period(None, cur, {}, "2026-01-01", "2026-01-31")
        core.assert_called_once_with(cur, "2026-01-01", "2026-02-01")
        self.assertEqual(result["totals"], {"revenue": 100, "cogs": 30, "exp": 20, "profit": 50})
        self.assertIsNone(result["items"][0]["min_price"])
        self.assertEqual(result["items"][0]["offer_id"], "A")
        cur.execute.assert_not_called()

    def test_year_boundary(self):
        with patch.object(summary, "sku_economics", return_value={"skus": {}}) as core:
            result = summary.build_period(None, None, {}, "2026-12-01", "2026-12-31")
        core.assert_called_once_with(None, "2026-12-01", "2027-01-01")
        self.assertEqual(result["items"], [])

    def test_core_error_not_hidden(self):
        with patch.object(summary, "sku_economics", side_effect=RuntimeError("core failed")):
            with self.assertRaisesRegex(RuntimeError, "core failed"):
                summary.build_period(None, None, {}, "2026-01-01", "2026-01-31")

    def test_build_closes_on_error_and_never_authorizes_sheets(self):
        conn = Mock()
        with patch.object(summary, "connect", return_value=conn), \
             patch.object(summary, "_load_offer_map", return_value={}), \
             patch.object(summary, "build_period", side_effect=RuntimeError("failed")), \
             patch.object(summary.gspread, "authorize") as authorize:
            with self.assertRaises(RuntimeError):
                summary.build()
        conn.close.assert_called_once_with()
        authorize.assert_not_called()

    def test_main_closes_before_any_sheets_on_error(self):
        conn = Mock()
        with patch.object(summary, "connect", return_value=conn), \
             patch.object(summary, "_load_offer_map", side_effect=RuntimeError("failed")), \
             patch.object(summary.gspread, "authorize") as authorize:
            with self.assertRaises(RuntimeError):
                summary.main()
        conn.close.assert_called_once_with()
        authorize.assert_not_called()

    def test_build_success_closes_and_does_not_publish(self):
        conn = Mock()
        with patch.object(summary, "connect", return_value=conn), \
             patch.object(summary, "_load_offer_map", return_value={}), \
             patch.object(summary, "sku_economics", return_value=economics()), \
             patch.object(summary.gspread, "authorize") as authorize:
            result = summary.build()
        self.assertEqual(result["total_profit"], 50)
        conn.close.assert_called_once_with()
        authorize.assert_not_called()
