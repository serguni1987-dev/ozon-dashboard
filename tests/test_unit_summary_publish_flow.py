import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import Mock, patch
from unitka import calc_unit_summary as summary


class SummaryPublishFlowTests(unittest.TestCase):
    @contextmanager
    def flow(self):
        conn = Mock()
        ws = Mock(id=123, row_count=5, col_count=12)
        settings = Mock()
        sh = Mock()
        def worksheet(title):
            if title == "Юнит-сводка":
                return ws
            if title == "НАСТРОЙКИ":
                return settings
            raise AssertionError("Unexpected worksheet: " + title)
        sh.worksheet.side_effect = worksheet
        client = Mock()
        client.open_by_key.return_value = sh
        block = {"items": [], "totals": {"revenue": 100, "cogs": 30, "exp": 20, "profit": 50}}
        with ExitStack() as stack:
            connect = stack.enter_context(patch.object(summary, "connect", return_value=conn))
            stack.enter_context(patch.object(summary, "_load_offer_map", return_value={}))
            stack.enter_context(patch.object(summary, "_source_dates", return_value={}))
            stack.enter_context(patch.object(summary, "_periods", return_value=[("TEST", "2026-11-01", "2026-11-14")]))
            stack.enter_context(patch.object(summary, "build_period", return_value=block))
            render = stack.enter_context(patch.object(summary, "render_rows", return_value=([["TEST"]], [(0, "title")])))
            creds = stack.enter_context(patch.object(summary.Credentials, "from_service_account_file", return_value=object()))
            authorize = stack.enter_context(patch.object(summary.gspread, "authorize", return_value=client))
            stack.enter_context(patch("builtins.print"))
            yield conn, ws, settings, sh, client, render, creds, authorize

    def test_success_target_values_formatting_and_status(self):
        with self.flow() as (conn, ws, settings, sh, client, render, creds, authorize):
            events = []
            conn.close.side_effect = lambda: events.append("close")
            render.side_effect = lambda *args: (events.append("render") or ([["TEST"]], [(0, "title")]))
            authorize.side_effect = lambda *args: (events.append("authorize") or client)
            ws.update.side_effect = lambda **kwargs: events.append("values")
            sh.batch_update.side_effect = lambda *args, **kwargs: events.append("format")
            settings.update.side_effect = lambda **kwargs: events.append("status")
            summary.main()
            self.assertEqual(events, ["close", "render", "authorize", "values", "format", "status"])
            client.open_by_key.assert_called_once_with(summary.SHEET_ID)
            self.assertEqual([c.args[0] for c in sh.worksheet.call_args_list], ["Юнит-сводка", "НАСТРОЙКИ"])
            sh.add_worksheet.assert_not_called()
            ws.clear.assert_not_called()
            ws.update.assert_called_once()
            self.assertEqual(ws.update.call_args.kwargs["value_input_option"], "RAW")
            self.assertEqual(ws.update.call_args.kwargs["range_name"], "A1")
            requests = sh.batch_update.call_args.args[0]["requests"]
            self.assertTrue(requests)
            for request in requests:
                body = next(iter(request.values()))
                self.assertEqual(body["range"]["sheetId"], 123)
            self.assertEqual(settings.update.call_args.kwargs["range_name"], "E8:H8")
            self.assertIn("полнота данных не подтверждена", str(settings.update.call_args))

    def test_value_failure_stops_formatting_and_status(self):
        with self.flow() as (conn, ws, settings, sh, client, render, creds, authorize):
            ws.update.side_effect = RuntimeError("value write failed")
            with self.assertRaisesRegex(RuntimeError, "value write failed"):
                summary.main()
            sh.batch_update.assert_not_called()
            settings.update.assert_not_called()
            self.assertEqual(sh.worksheet.call_count, 1)
            ws.clear.assert_not_called()

    def test_format_failure_stops_status(self):
        with self.flow() as (conn, ws, settings, sh, client, render, creds, authorize):
            sh.batch_update.side_effect = RuntimeError("format failed")
            with self.assertRaisesRegex(RuntimeError, "format failed"):
                summary.main()
            ws.update.assert_called_once()
            settings.update.assert_not_called()

    def test_status_failure_is_currently_nonfatal(self):
        with self.flow() as (conn, ws, settings, sh, client, render, creds, authorize):
            settings.update.side_effect = RuntimeError("status failed")
            summary.main()
            ws.update.assert_called_once()
            sh.batch_update.assert_called_once()
            settings.update.assert_called_once()

    def test_invalid_render_prevents_authorization(self):
        with self.flow() as (conn, ws, settings, sh, client, render, creds, authorize):
            render.return_value = ([[float("nan")]], [])
            with self.assertRaises(ValueError):
                summary.main()
            creds.assert_not_called()
            authorize.assert_not_called()
            ws.update.assert_not_called()
            conn.close.assert_called_once_with()
