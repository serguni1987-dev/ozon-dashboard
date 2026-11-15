import ast
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock
from unitka.purchase_candidates import forecast_candidates, candidate_text


class PulsePurchaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "unitka" / "calc_pulse.py"
        self.tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        names = {"_load_purchase_recommendations", "_purchase_rows"}
        nodes = [n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        self.ns = {"forecast_candidates": forecast_candidates, "candidate_text": candidate_text}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), self.ns)
        self.con = sqlite3.connect(":memory:")
        self.addCleanup(self.con.close)
        self.con.executescript("CREATE TABLE forecast(sku,forecast_qty,forecast_revenue); CREATE TABLE products(sku,offer_id);")
        self.proxy = Mock(wraps=self.con)
        self.ns["connect"] = Mock(return_value=self.proxy)

    def load(self):
        return self.ns["_load_purchase_recommendations"]()

    def add(self):
        self.con.execute("INSERT INTO forecast VALUES('123',10,1000)")
        self.con.execute("INSERT INTO products VALUES(123,'ART')")

    def test_identifiers(self):
        self.add()
        row = self.load()[0]
        self.assertEqual((row["sku"], row["offer_id"]), ("123", "ART"))
        self.assertIs(row["purchase_approved"], False)

    def test_close_on_success(self):
        self.load()
        self.proxy.close.assert_called_once()

    def test_read_error_not_empty_success(self):
        self.con.execute("DROP TABLE forecast")
        with self.assertRaises(sqlite3.OperationalError): self.load()
        self.proxy.close.assert_called_once()

    def test_cursor_error_closes(self):
        self.proxy.cursor.side_effect = RuntimeError("cursor failed")
        with self.assertRaises(RuntimeError): self.load()
        self.proxy.close.assert_called_once()

    def test_duplicate_forecast(self):
        self.add()
        self.con.execute("INSERT INTO forecast VALUES('123',20,2000)")
        self.assertEqual(self.load(), [])

    def test_duplicate_product_mapping(self):
        self.add()
        self.con.execute("INSERT INTO products VALUES(123,'OTHER')")
        self.assertEqual(self.load(), [])

    def test_missing_product_and_revenue(self):
        self.con.execute("INSERT INTO forecast VALUES('123',10,NULL)")
        row = self.load()[0]
        self.assertEqual((row["sku"], row["offer_id"]), ("123", ""))
        self.assertIsNone(row["forecast_revenue"])

    def test_render_is_not_purchase_directive(self):
        self.add()
        rows = self.ns["_purchase_rows"](self.load())
        text = str(rows)
        self.assertNotIn("закупить", text.lower())
        self.assertIn("Закупка не согласована", text)
        self.assertTrue(all(len(row) == 5 for row in rows))

    def test_empty_render(self):
        self.assertIn("закупка не согласована", str(self.ns["_purchase_rows"]([])))

    def test_main_wiring(self):
        main = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_purchase_rows" for n in ast.walk(main)))
        self.assertFalse(any(isinstance(n, ast.Constant) and isinstance(n.value, str) and ": закупить " in n.value for n in ast.walk(main)))


if __name__ == "__main__": unittest.main()
