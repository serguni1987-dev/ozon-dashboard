import sqlite3
from . import config

DB = str(config.DB_PATH)
con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE IF NOT EXISTS postings_daily (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    posting_number TEXT NOT NULL,
    sku            TEXT,
    quantity       INTEGER DEFAULT 1,
    price          REAL DEFAULT 0,
    commission     REAL DEFAULT 0,
    is_cancelled   INTEGER DEFAULT 0,
    is_returned    INTEGER DEFAULT 0,
    status         TEXT,
    source         TEXT DEFAULT 'api',
    raw_json       TEXT
);
CREATE INDEX IF NOT EXISTS idx_postings_date    ON postings_daily(date);
CREATE INDEX IF NOT EXISTS idx_postings_posting ON postings_daily(posting_number);
""")
con.commit()
con.close()
print("[OK] postings_daily ready")