"""Web adapter tests without Streamlit startup, network or production DB."""
import ast
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


WEB = Path(__file__).resolve().parents[1] / "unitka" / "web_app.py"


def adapters():
    tree = ast.parse(WEB.read_text(encoding="utf-8-sig"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"get_db_schema", "execute_sql"}]
    for node in functions:
        node.decorator_list = []
    module = ast.Module(body=functions, type_ignores=[])
    ns = {"config": types.SimpleNamespace(DB_PATH="fixture.db"),
          "get_schema": Mock(return_value="filtered schema"),
          "read_query": Mock(return_value=[{"month":"2026-10"}]),
          "pd": types.SimpleNamespace(DataFrame=Mock(side_effect=lambda rows: rows))}
    exec(compile(ast.fix_missing_locations(module), str(WEB), "exec"), ns)
    return ns


class WebSQLSafetyTests(unittest.TestCase):
    def test_schema_delegates_to_shared_guard(self):
        ns = adapters()
        self.assertEqual(ns["get_db_schema"]((1,)), "filtered schema")
        ns["get_schema"].assert_called_once_with("fixture.db")

    def test_query_delegates_with_limits(self):
        ns = adapters()
        self.assertEqual(ns["execute_sql"]("SELECT month FROM monthly_reports", (1,)), [{"month":"2026-10"}])
        ns["read_query"].assert_called_once_with("fixture.db", "SELECT month FROM monthly_reports", max_rows=100, seconds=2.0)

    def test_denial_propagates(self):
        ns = adapters()
        ns["read_query"].side_effect = sqlite3.DatabaseError("denied")
        with self.assertRaises(sqlite3.DatabaseError):
            ns["execute_sql"]("SELECT net_profit FROM monthly_reports", (1,))
        ns["pd"].DataFrame.assert_not_called()

    def test_empty_result(self):
        ns = adapters(); ns["read_query"].return_value = []
        self.assertEqual(ns["execute_sql"]("SELECT 1 WHERE 0", (1,)), [])

    def test_no_local_sql_connection_or_authorizer(self):
        source = WEB.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertNotIn("open_readonly", names)
        self.assertNotIn("authorize", names)
        self.assertIn("from unitka.ai_sql_safety import get_schema, read_query", source)
        self.assertNotIn("sqlite3.connect", source)

    def test_ui_no_longer_promises_loss_analysis(self):
        source = WEB.read_text(encoding="utf-8-sig")
        self.assertNotIn("покажи убыточные товары", source)
        self.assertIn("Не вычисляй прибыль, налоги", source)
        self.assertIn('raw.startswith("CANNOT_ANSWER")', source)

    def test_abc_fixture_connection_explicitly_closed(self):
        path = WEB.parents[1] / "tests" / "test_abc_finance.py"
        source = path.read_text(encoding="utf-8-sig")
        self.assertIn('contextlib.closing(sqlite3.connect(":memory:"))', source)

    def test_sqlite_context_manager_vs_closing(self):
        import contextlib
        with sqlite3.connect(":memory:") as open_conn:
            open_conn.execute("SELECT 1")
        try:
            self.assertEqual(open_conn.execute("SELECT 1").fetchone(), (1,))
        finally:
            open_conn.close()
        with contextlib.closing(sqlite3.connect(":memory:")) as closed_conn:
            closed_conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            closed_conn.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
