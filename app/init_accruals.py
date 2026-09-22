"""
init_accruals.py — создаёт таблицу accruals для накопления
финансовых данных из /v1/finance/accrual/by-day.
"""
import sqlite3

DB = "ozon.db"

con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE IF NOT EXISTS accruals (
    accrual_id      INTEGER PRIMARY KEY,
    date            TEXT NOT NULL,
    sku             INTEGER,
    unit_number     TEXT,
    accrued_category TEXT,
    delivery_schema TEXT,
    seller_price    REAL,
    sale_price      REAL,
    sale_commission REAL,
    bonus           REAL,
    coinvestment    REAL,
    total_amount    REAL
);
CREATE INDEX IF NOT EXISTS idx_accruals_date ON accruals(date);
CREATE INDEX IF NOT EXISTS idx_accruals_sku  ON accruals(sku);

CREATE TABLE IF NOT EXISTS accruals_services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    accrual_id   INTEGER NOT NULL,
    date         TEXT NOT NULL,
    sku          INTEGER,
    type_id      INTEGER NOT NULL,
    type_name    TEXT,
    amount       REAL NOT NULL,
    FOREIGN KEY (accrual_id) REFERENCES accruals(accrual_id)
);
CREATE INDEX IF NOT EXISTS idx_services_date ON accruals_services(date);
CREATE INDEX IF NOT EXISTS idx_services_type ON accruals_services(type_id);
""")
con.commit()
con.close()
print("[OK] Таблицы accruals и accruals_services созданы")
