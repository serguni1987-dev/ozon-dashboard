"""Expense-only SKU integration through actual load_period/build functions; no APIs."""
import ast
import contextlib
from datetime import datetime, timedelta
import hashlib
import io
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "unitka" / "calc_margin.py"


def runtime(path):
    names = {"_f", "_whole_months", "load_period", "load_stocks", "calc_derived", "build"}
    constants = {"HEADER", "SERVICE_GROUPS", "MIN_TAX_PCT"}
    nodes = []
    for node in ast.parse(SOURCE.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            nodes.append(node)
    calls = []
    real_connect = sqlite3.connect
    def connect(*args, **kwargs):
        con = real_connect(path.resolve().as_uri()+"?mode=ro", uri=True)
        con.execute("PRAGMA query_only=ON")
        calls.append(con)
        return con
    core = types.SimpleNamespace(sku_economics=lambda *a: {"skus":{
        1:dict(delivered=1,returned=0,income=2000,commission=100,units=1)}})
    ns = dict(datetime=datetime, timedelta=timedelta, DB=str(path),
        sqlite3=types.SimpleNamespace(connect=connect,Row=sqlite3.Row),
        REGIME_DR="Д-Р",REGIME_INCOME="Доходы", unit_core=core,
        load_min_prices=lambda *a: {}, ozon_pnl=lambda *a:{"ozon_total":1000})
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),"exec"),ns)
    return ns, calls


class MarginExpenseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"fixture.db"
        with contextlib.closing(sqlite3.connect(self.path)) as con:
            con.executescript("""
                CREATE TABLE postings_daily(sku INTEGER,date TEXT,quantity INTEGER,is_cancelled INTEGER,is_returned INTEGER,status TEXT);
                CREATE TABLE realization_daily(sku INTEGER,date TEXT,posting_number TEXT,quantity INTEGER,seller_price REAL,sale_price REAL,bonus REAL,coinvestment REAL,commission REAL,delivery_total REAL);
                CREATE TABLE accrual_sku_daily(sku INTEGER,date TEXT,type_id INTEGER,amount REAL);
                CREATE TABLE accrual_non_item_daily(date TEXT,posting_number TEXT,type_id INTEGER,amount REAL);
                CREATE TABLE product_cost_history(sku INTEGER,date_from TEXT,cost_price REAL);
                CREATE TABLE products(sku INTEGER,category_l1 TEXT,name TEXT,offer_id TEXT);
                CREATE TABLE current_stocks(sku INTEGER,offer_id TEXT,fbo_present INTEGER,fbs_present INTEGER);
                INSERT INTO realization_daily VALUES(1,'2026-10-05','P',1,2000,2000,0,0,-100,0);
                INSERT INTO product_cost_history VALUES(1,'2026-01-01',400);
                INSERT INTO products VALUES(1,'Category','Sold','ONE');
                INSERT INTO products VALUES(2,'Category','Expense only','TWO');
            """)
            con.commit()
        self.ns,self.connections=runtime(self.path)
        self.addCleanup(self.close_connections)

    def close_connections(self):
        for con in self.connections:
            con.close()

    def insert(self,sql,params=()):
        with contextlib.closing(sqlite3.connect(self.path)) as con:
            con.execute(sql,params);con.commit()

    def fee(self,sku=2,amount=-705.09,day="2026-10-02",tid=32):
        self.insert("INSERT INTO accrual_sku_daily VALUES(?,?,?,?)",(sku,day,tid,amount))

    def build(self,rate=5,regime="Д-Р"):
        with contextlib.redirect_stdout(io.StringIO()):
            result=self.ns["build"]("2026-10-01","2026-10-31",rate,{"regime":regime})
        self.assertEqual(result[0],self.ns["HEADER"])
        for row in result[1:]:
            self.assertEqual(len(row),len(result[0]))
        return {row[0]:dict(zip(result[0],row)) for row in result[1:]}

    def test_expense_only_reaches_final_sheet_rows(self):
        self.fee();rows=self.build()
        self.assertEqual(set(rows),{1,2})
        row=rows[2]
        self.assertEqual(row["Выручка, руб."],0)
        self.assertEqual(row["Выкупы, шт."],0)
        self.assertEqual(row["Себестоимость, руб."],0)
        self.assertEqual(row["Логистика МП, руб."],705.09)
        self.assertEqual(row["Прибыль, руб."],-705.09)
        self.assertEqual(row["Налоги, руб."],0)
        self.assertEqual(row["Артикул товара"],"TWO")

    def test_total_before_tax_unchanged(self):
        before=self.build();self.fee();after=self.build()
        def total(rows):
            return sum(r["Маржа, руб."]-r["Доп. расходы (общие расходы Ozon: реклама и пр.), руб."] for r in rows.values())
        self.assertAlmostEqual(total(before),600,places=2)
        self.assertAlmostEqual(total(after),600,places=2)
        self.assertAlmostEqual(after[1]["Доп. расходы (общие расходы Ozon: реклама и пр.), руб."],194.91,places=2)

    def test_tax_columns_recomputed_not_frozen(self):
        before=self.build();self.fee();after=self.build()
        self.assertEqual(before[1]["Налоги, руб."],30)
        self.assertEqual(after[1]["Налоги, руб."],65.25)
        self.assertEqual(after[1]["Прибыль, руб."],1239.84)
        self.assertEqual(after[2]["Налоги, руб."],0)

    def test_income_regime_unchanged(self):
        before=self.build(regime="Доходы");self.fee();after=self.build(regime="Доходы")
        self.assertEqual(before[1]["Налоги, руб."],100)
        self.assertEqual(after[1]["Налоги, руб."],100)
        self.assertEqual(after[2]["Налоги, руб."],0)

    def test_existing_sku_fee_not_doubled(self):
        self.fee(sku=1,amount=-10);self.fee()
        rows=self.build()
        self.assertEqual(rows[1]["Логистика МП, руб."],10)
        self.assertEqual(rows[2]["Логистика МП, руб."],705.09)

    def test_outside_period_and_unassigned_omitted(self):
        self.fee(day="2026-09-30");self.fee(sku=3,day="2026-11-01")
        self.fee(sku=None);self.fee(sku=0)
        self.assertEqual(set(self.build()),{1})

    def test_fine_attribution_preserved(self):
        self.fee()
        self.insert("INSERT INTO accrual_non_item_daily VALUES('2026-10-05','P',94,-79.18)")
        rows=self.build()
        self.assertEqual(rows[1]["Прочие расходы МП, руб."],79.18)
        self.assertEqual(rows[2]["Логистика МП, руб."],705.09)

    def test_database_unchanged_and_connection_closed(self):
        self.fee();before=hashlib.sha256(self.path.read_bytes()).digest()
        self.build()
        self.assertEqual(before,hashlib.sha256(self.path.read_bytes()).digest())
        with self.assertRaises(sqlite3.ProgrammingError):
            self.connections[-1].execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
