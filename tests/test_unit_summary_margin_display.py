import unittest
from unittest.mock import patch
from unitka import calc_unit_summary as summary


class SummaryMarginDisplayTests(unittest.TestCase):
    def result(self, revenue, profit):
        eco = {"skus": {1: {"income": revenue, "cogs": 0,
               "commission": revenue - profit, "svc_fixed": 0,
               "svc_pct": 0, "overhead": 0, "profit": profit}}}
        with patch.object(summary, "sku_economics", return_value=eco):
            return summary.build_period(None, None, {}, "2026-11-01", "2026-11-14")

    def test_negative_revenue(self):
        result = self.result(-3177, -600.61)
        self.assertIsNone(result["items"][0]["margin"])
        self.assertEqual(result["items"][0]["status"], "Убыточный")
        self.assertEqual(result["totals"]["profit"], -600.61)

    def test_zero_revenue(self):
        self.assertIsNone(self.result(0, -100)["items"][0]["margin"])

    def test_positive_revenue(self):
        self.assertEqual(self.result(100, -20)["items"][0]["margin"], -20)

    def test_render_nonpositive_and_positive_revenue(self):
        for revenue, profit, expected in ((-3177, -600.61, "н/д"), (0, -100, "н/д"), (100, -20, -20.0)):
            with self.subTest(revenue=revenue):
                block = self.result(revenue, profit)
                block.update(title="TEST", **{"from": "2026-11-01", "to": "2026-11-14"})
                rows, _ = summary.render_rows([block], "TEST", {})
                totals = next(row for row in rows if len(row) == 8 and row[0] == "TEST")
                detail = next(row for row in rows if len(row) == 9 and row[1] == 1)
                self.assertEqual(totals[7], expected)
                self.assertEqual(detail[7], expected)
                self.assertEqual(detail[6], "")
                self.assertTrue(any("Маржа не рассчитывается" in str(row) for row in rows))
