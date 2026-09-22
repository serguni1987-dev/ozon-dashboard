"""
init_price_changes.py — таблица для лога изменений цен.
"""
import sqlite3

con = sqlite3.connect("ozon.db")
con.executescript("""
CREATE TABLE IF NOT EXISTS price_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at   TEXT NOT NULL,
    offer_id     TEXT NOT NULL,
    sku          INTEGER,
    old_price    REAL,
    new_price    REAL,
    min_price    REAL,
    api_status   TEXT,      -- 'ok', 'error', 'partial'
    api_message  TEXT,
    batch_id     TEXT,      -- группировка по одному вызову API
    rolled_back  INTEGER DEFAULT 0,
    rollback_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_pc_offer ON price_changes(offer_id);
CREATE INDEX IF NOT EXISTS idx_pc_changed ON price_changes(changed_at);
CREATE INDEX IF NOT EXISTS idx_pc_rolled ON price_changes(rolled_back);
""")
con.commit()
con.close()
print("[OK] Таблица price_changes создана")
