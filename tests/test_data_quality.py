"""Run: py -m unittest discover -s tests -p test_data_quality.py -v"""
import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unitka.data_quality import inspect_database, backup_database, readonly


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "source.db"
        with closing(sqlite3.connect(self.db)) as con:
            con.executescript("""CREATE TABLE abc_xyz(period TEXT,sku INTEGER,profit REAL,fetched_at TEXT);
            INSERT INTO abc_xyz VALUES ('a',1,10,'2026-11-01'),('a',1,10,'2026-11-01'),('b',1,NULL,'2026-11-02');
            CREATE TABLE product_cost_history(sku INTEGER,date_from TEXT,cost_price REAL);
            INSERT INTO product_cost_history VALUES (1,'2026-01-01',10);
            CREATE TABLE postings_daily(sku INTEGER,date TEXT);
            INSERT INTO postings_daily VALUES (2,'2026-11-01');""")
            con.commit()

    def test_checks_and_source_unchanged(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        report = inspect_database(self.db)
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())
        checks = {c['check']: c for c in report['checks']}
        self.assertEqual(checks['abc_duplicate_period_sku']['details'][0][0], 1)
        self.assertEqual(checks['abc_missing_profit']['details'][0][0], 1)
        self.assertEqual(checks['postings_without_positive_historical_cost']['details'][0][0], 1)
        self.assertFalse(report['can_reprice'])

    def test_missing_database_not_created(self):
        path = self.db.parent / 'missing.db'
        with self.assertRaises(sqlite3.OperationalError):
            inspect_database(path)
        self.assertFalse(path.exists())

    def test_readonly(self):
        with closing(readonly(self.db)) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute('DELETE FROM abc_xyz')

    def test_backup_and_overwrite_protection(self):
        target = self.db.parent / 'backup.db'
        backup_database(self.db, target)
        with closing(sqlite3.connect(target)) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM abc_xyz').fetchone()[0],3)
        with self.assertRaises(FileExistsError):
            backup_database(self.db, target)
        with self.assertRaises(ValueError):
            backup_database(self.db, self.db)

    def test_wal_backup(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute("INSERT INTO abc_xyz VALUES ('c',3,-1,'2026-11-03')")
            con.commit()
            target=self.db.parent/'wal_backup.db'
            backup_database(self.db,target)
            with closing(sqlite3.connect(target)) as dst:
                self.assertEqual(dst.execute('SELECT COUNT(*) FROM abc_xyz').fetchone()[0],4)


if __name__ == '__main__':
    unittest.main()
