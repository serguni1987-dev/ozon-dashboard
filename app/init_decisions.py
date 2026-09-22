"""
init_decisions.py — создаёт таблицу decisions для дневника.
"""
import sqlite3

con = sqlite3.connect("ozon.db")
con.executescript("""
CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    offer_id      TEXT NOT NULL,
    category      TEXT,
    action_text   TEXT,
    -- Снимок метрик на момент решения
    revenue_before   REAL,
    profit_before    REAL,
    margin_before    REAL,
    orders_before    INTEGER,
    views_before     INTEGER,
    carts_before     INTEGER,
    price_before     REAL,
    -- Что изменили
    price_after      REAL,
    -- Статус
    status        TEXT DEFAULT 'in_progress',
    review_at     TEXT,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_offer ON decisions(offer_id);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
""")
con.commit()
con.close()
print("[OK] Таблица decisions создана")
