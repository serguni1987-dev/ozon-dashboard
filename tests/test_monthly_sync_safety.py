import ast
import json
import math
import sqlite3
import tempfile
import types
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class MonthlySyncSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test.db'
        self.connections = []
        outer = self
        class TrackingConnection(sqlite3.Connection):
            def close(self):
                self.was_closed = True
                super().close()
        def connect(path):
            conn = sqlite3.connect(path, factory=TrackingConnection)
            conn.was_closed = False
            outer.connections.append(conn)
            return conn
        tree = ast.parse((ROOT / 'app/sync_monthly.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'init_tables','to_float','main'}]
        self.request = Mock()
        self.scope = {'sqlite3': types.SimpleNamespace(connect=connect), 'requests': self.request,
            'json': json, 'math': math, 'datetime': datetime, 'DB': str(self.db),
            'URL': 'https://example.invalid', 'H': {}, 'TAX_RATE': 0.15}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'monthly_test', 'exec'), self.scope)
        with closing(sqlite3.connect(self.db)) as conn:
            self.scope['init_tables'](conn)

    def invoke(self, rows=None, data=None, status=200, force=False):
        response = Mock(status_code=status)
        response.json.return_value = data if data is not None else {'result': {'header': {'start_date':'2026-10-01','stop_date':'2026-10-31'}, 'rows': rows if rows is not None else [self.row()]}}
        self.request.post.return_value = response
        argv = ['sync_monthly.py', '--month', '2026-10'] + (['--force'] if force else [])
        with patch('sys.argv', argv), patch('builtins.print'):
            self.scope['main']()

    def row(self):
        return {'item': {'sku': 1}, 'delivery_commission': {'amount': 100, 'quantity': 1}}

    def test_http_error_fails_before_connect(self):
        with self.assertRaises(RuntimeError):
            self.invoke(status=503)
        self.assertEqual(self.connections, [])

    def test_invalid_response_shapes(self):
        for data in ([], {}, {'result': []}, {'result': {'header': [], 'rows': []}}, {'result': {'header': {}, 'rows': {}}}):
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                self.invoke(data=data)
        self.assertEqual(self.connections, [])

    def test_empty_report_is_not_success(self):
        with self.assertRaises(RuntimeError):
            self.invoke(rows=[])
        self.assertEqual(self.connections, [])

    def test_invalid_row_shape(self):
        for row in (None, {'item': []}, {'delivery_commission': []}):
            with self.subTest(row=row), self.assertRaises(RuntimeError):
                self.invoke(rows=[row])
        self.assertEqual(self.connections, [])

    def test_invalid_amounts_are_not_zeroed(self):
        for value in ('bad', 'NaN', float('inf'), True, []):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.scope['to_float'](value)

    def test_success_saves_header_and_rows_and_closes(self):
        self.invoke()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM monthly_reports').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM monthly_realization_rows').fetchone()[0], 1)
        self.assertTrue(all(c.was_closed for c in self.connections))

    def test_existing_month_without_force_is_preserved(self):
        self.invoke()
        self.invoke(rows=[self.row(), self.row()])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM monthly_realization_rows').fetchone()[0], 1)
        self.assertTrue(all(c.was_closed for c in self.connections))

    def test_force_failure_restores_old_header_and_rows(self):
        self.invoke()
        with closing(sqlite3.connect(self.db)) as conn:
            before = (conn.execute('SELECT * FROM monthly_reports').fetchall(), conn.execute('SELECT * FROM monthly_realization_rows').fetchall())
        bad = self.row()
        bad['delivery_commission']['amount'] = 'bad'
        with self.assertRaises(ValueError):
            self.invoke(rows=[self.row(), bad], force=True)
        with closing(sqlite3.connect(self.db)) as conn:
            after = (conn.execute('SELECT * FROM monthly_reports').fetchall(), conn.execute('SELECT * FROM monthly_realization_rows').fetchall())
        self.assertEqual(before, after)
        self.assertTrue(all(c.was_closed for c in self.connections))

    def test_connection_closes_on_row_conversion_failure(self):
        bad = self.row()
        bad['delivery_commission']['quantity'] = 'bad'
        with self.assertRaises(ValueError):
            self.invoke(rows=[bad])
        self.assertTrue(self.connections)
        self.assertTrue(all(c.was_closed for c in self.connections))
