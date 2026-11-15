"""One-time pulse integration. No database, network or Sheets calls."""
import ast
import hashlib
from pathlib import Path

EXPECTED = "27db41c5298c45f9a7db89f7d5a58dfa700a628d"
LOADER = '''def _load_purchase_recommendations():
    """Forecast candidates only; database errors must remain visible."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT f.sku, p.offer_id, f.forecast_qty, f.forecast_revenue FROM forecast f LEFT JOIN products p ON p.sku = CAST(f.sku AS INTEGER)")
        rows = [{"sku": r[0], "offer_id": r[1], "forecast_qty": r[2], "forecast_revenue": r[3]} for r in cur.fetchall()]
        return forecast_candidates(rows)[:5]
    finally:
        conn.close()


def _purchase_rows(purchases):
    rows = [["ПРОГНОЗ СПРОСА: КАНДИДАТЫ НА ПРОВЕРКУ (топ-5)", "", "", "", ""]]
    rows.append(["Это не план закупки. Остатки и полная экономика требуют проверки.", "", "", "", ""])
    if purchases:
        rows.extend([[candidate_text(p), "", "", "", ""] for p in purchases])
    else:
        rows.append(["В прогнозе нет подходящих кандидатов; закупка не согласована.", "", "", "", ""])
    rows.append(["", "", "", "", ""])
    return rows
'''
TESTS = '''import ast
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
'''


def prepare(raw):
    normalized = raw.replace(b"\r\n", b"\n")
    blob = hashlib.sha1(b"blob " + str(len(normalized)).encode() + b"\0" + normalized).hexdigest()
    if blob != EXPECTED:
        raise ValueError("Source differs from reviewed version; no files changed")
    text = normalized.decode("utf-8-sig")
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_load_purchase_recommendations")
    lines = text.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = [LOADER]
    text = "".join(lines)
    anchor = "from . import calc_funnel\n"
    if text.count(anchor) != 1:
        raise ValueError("Import context differs; no files changed")
    text = text.replace(anchor, anchor + "from .purchase_candidates import forecast_candidates, candidate_text\n")
    start = text.index("    # 5. Закупки\n")
    end = text.index("    # 6. Ассортимент\n", start)
    text = text[:start] + '    # 5. Forecast candidates are not approved purchases.\n    values.extend(_purchase_rows(res["purchases"]))\n\n' + text[end:]
    old = '    print(f"  Закупок: {len(res[\'purchases\'])}")'
    new = '    print(f"  Кандидатов прогноза (не план закупки): {len(res[\'purchases\'])}")'
    if text.count(old) != 1:
        raise ValueError("Output context differs; no files changed")
    text = text.replace(old, new)
    ast.parse(text)
    ast.parse(TESTS)
    return text


def main():
    root = Path(__file__).resolve().parent
    target = root / "unitka" / "calc_pulse.py"
    tests = root / "tests" / "test_pulse_purchase_integration.py"
    if not (root / "unitka" / "purchase_candidates.py").is_file():
        raise SystemExit("Missing purchase_candidates.py; update agreed branch first")
    if tests.exists():
        raise SystemExit("Test file already exists; no files changed")
    raw = target.read_bytes()
    try:
        text = prepare(raw)
    except (ValueError, StopIteration, SyntaxError) as exc:
        raise SystemExit(str(exc)) from exc
    if not tests.parent.is_dir():
        raise SystemExit("Tests directory missing; no files changed")
    backup = root / "out" / "source_backups" / "calc_pulse_before_purchase_integration.py.bak"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb") as f:
        f.write(raw)
    with tests.open("x", encoding="utf-8", newline="\n") as f:
        f.write(TESTS)
    with target.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("Updated calc_pulse.py and added 10 tests. No DB, API or Sheets calls.")
    print("Not committed. Run full test suite and inspect diff before committing.")


if __name__ == "__main__": main()
