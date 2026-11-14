"""Offline guard tests: no Google, Ollama, Ozon or production DB."""
import ast
import hashlib
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unitka import ai_sql_safety as safety
from unitka import chat_in_sheets as sheets


class AISQLSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "test.db"
        con = sqlite3.connect(self.db)
        try:
            con.executescript("""
                CREATE TABLE monthly_reports(month TEXT, sale_price_sum REAL,
                    bonus_sum REAL, net_profit REAL, raw_json TEXT);
                INSERT INTO monthly_reports VALUES('2026-10',100,20,999,'secret');
                CREATE TABLE secret(value TEXT);
                INSERT INTO secret VALUES('secret');
                CREATE VIEW hidden_view AS SELECT * FROM monthly_reports;
            """)
            con.commit()
        finally:
            con.close()

    def query(self, sql, **kwargs):
        return safety.read_query(self.db, sql, **kwargs)

    def test_allowed_read(self):
        self.assertEqual(self.query("SELECT month FROM monthly_reports"), [{"month":"2026-10"}])

    def test_aggregate(self):
        self.assertEqual(self.query("SELECT SUM(sale_price_sum) AS value FROM monthly_reports"), [{"value":100.0}])

    def test_cte(self):
        self.assertEqual(self.query("WITH x AS (SELECT month FROM monthly_reports) SELECT month FROM x")[0]["month"], "2026-10")

    def test_writes_blocked(self):
        for sql in ("DELETE FROM monthly_reports", "UPDATE monthly_reports SET net_profit=0", "CREATE TABLE x(a)", "WITH x AS (SELECT 1) DELETE FROM monthly_reports"):
            with self.subTest(sql=sql), self.assertRaises((ValueError, sqlite3.Error)):
                self.query(sql)

    def test_pragmas_attach_blocked(self):
        for sql in ("PRAGMA writable_schema=ON", "ATTACH ':memory:' AS other", "VACUUM"):
            with self.subTest(sql=sql), self.assertRaises((ValueError, sqlite3.Error)):
                self.query(sql)

    def test_hidden_columns_blocked(self):
        for field in ("net_profit", "raw_json", "*"):
            with self.subTest(field=field), self.assertRaises(sqlite3.Error):
                self.query(f"SELECT {field} FROM monthly_reports")

    def test_hidden_column_in_where_blocked(self):
        with self.assertRaises(sqlite3.Error):
            self.query("SELECT month FROM monthly_reports WHERE net_profit>0")

    def test_other_tables_blocked(self):
        for table in ("secret", "sqlite_master", "hidden_view"):
            with self.subTest(table=table), self.assertRaises(sqlite3.Error):
                self.query(f"SELECT * FROM {table}")

    def test_functions_blocked(self):
        for sql in ("SELECT load_extension('x')", "SELECT randomblob(100)", "SELECT * FROM pragma_table_info('secret')"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.Error):
                self.query(sql)

    def test_multiple_statements_blocked(self):
        with self.assertRaises(sqlite3.Error):
            self.query("SELECT 1; DELETE FROM monthly_reports")

    def test_row_limit(self):
        with self.assertRaises(ValueError):
            self.query("WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<30) SELECT n FROM x", max_rows=20)

    def test_resource_limit(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.query("WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT SUM(n) FROM x", seconds=0.05)

    def test_missing_db_not_created(self):
        missing = self.db.with_name("missing.db")
        with self.assertRaises(sqlite3.Error):
            safety.read_query(missing,"SELECT 1")
        self.assertFalse(missing.exists())

    def test_schema_filtered(self):
        schema = safety.get_schema(self.db)
        self.assertIn("sale_price_sum", schema)
        for field in ("net_profit", "raw_json", "secret"):
            self.assertNotIn(field, schema)

    def test_file_unchanged(self):
        before = hashlib.sha256(self.db.read_bytes()).digest()
        self.query("SELECT COUNT(*) AS n FROM monthly_reports")
        with self.assertRaises(sqlite3.Error):
            self.query("SELECT net_profit FROM monthly_reports")
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).digest())

    def test_sheets_integration_and_prompt(self):
        source = inspect.getsource(sheets)
        tree = ast.parse(source)
        self.assertIn("read_query(config.DB_PATH",source)
        self.assertNotIn("from .db import connect",source)
        prompt = sheets.system_prompt("monthly_reports(month TEXT)")
        self.assertNotIn("124 246",prompt)
        self.assertNotIn("ноябрь 2026",prompt)
        self.assertIn("CANNOT_ANSWER",prompt)
        self.assertTrue(tree.body)


if __name__ == "__main__":
    unittest.main()
