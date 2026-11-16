import unittest
from unittest.mock import Mock, patch
from unitka import calc_unit_summary as summary


class SummaryWriteSafetyTests(unittest.TestCase):
    def test_padding_clears_old_tail_without_clear(self):
        ws = Mock(row_count=3, col_count=12)
        summary._write_report_values(ws, [["new"], []])
        values = ws.update.call_args.kwargs["values"]
        self.assertEqual(len(values), 3)
        self.assertTrue(all(len(row) == 12 for row in values))
        self.assertEqual(values[2], [""] * 12)
        self.assertEqual(ws.update.call_args.kwargs["value_input_option"], "RAW")
        ws.clear.assert_not_called()
        ws.resize.assert_not_called()

    def test_update_error_propagates_without_clear(self):
        ws = Mock(row_count=3, col_count=12)
        ws.update.side_effect = RuntimeError("write failed")
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            summary._write_report_values(ws, [["new"]])
        ws.clear.assert_not_called()

    def test_invalid_values_prevent_any_write(self):
        for rows in ([], [[float("nan")]], [[float("inf")]], [[None]], [[1] * 10]):
            with self.subTest(rows=rows):
                ws = Mock(row_count=3, col_count=12)
                with self.assertRaises(ValueError):
                    summary._write_report_values(ws, rows)
                self.assertEqual(ws.mock_calls, [])

    def test_invalid_markers(self):
        for marks in ([(1, "title")], [(0, "bad")], [(0, "title"), (0, "period")]):
            with self.assertRaises(ValueError):
                summary._validate_report([["x"]], marks)

    def test_render_error_before_credentials_and_sheets(self):
        conn = Mock()
        block = {"items": [], "totals": {"revenue": 0, "cogs": 0, "exp": 0, "profit": 0}}
        with patch.object(summary, "connect", return_value=conn), \
             patch.object(summary, "_load_offer_map", return_value={}), \
             patch.object(summary, "_source_dates", return_value={}), \
             patch.object(summary, "build_period", return_value=block), \
             patch.object(summary, "render_rows", side_effect=RuntimeError("render failed")), \
             patch.object(summary.Credentials, "from_service_account_file") as creds, \
             patch.object(summary.gspread, "authorize") as authorize:
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                summary.main()
        conn.close.assert_called_once_with()
        creds.assert_not_called()
        authorize.assert_not_called()
