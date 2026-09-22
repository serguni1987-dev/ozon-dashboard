"""
recreate_monthly_tables.py — удаляет старые таблицы и создаёт с новой схемой.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
print("Старая схема monthly_realization_rows:")
for r in con.execute("PRAGMA table_info(monthly_realization_rows)"):
    print(f"  {r[1]} {r[2]}")

# Удаляем
con.execute("DROP TABLE IF EXISTS monthly_realization_rows")
con.execute("DROP TABLE IF EXISTS monthly_reports")
con.commit()
print("\n[OK] Старые таблицы удалены")

# Создаём новые
con.executescript("""
CREATE TABLE monthly_reports (
    month            TEXT PRIMARY KEY,
    year             INTEGER,
    month_num        INTEGER,
    report_number    TEXT,
    report_date      TEXT,
    period_start     TEXT,
    period_end       TEXT,
    seller_price_sum     REAL DEFAULT 0,
    sale_price_sum       REAL DEFAULT 0,
    gross_commission_sum REAL DEFAULT 0,
    bonus_sum            REAL DEFAULT 0,
    coinvestment_sum     REAL DEFAULT 0,
    logistics_sum        REAL DEFAULT 0,
    total_held_sum       REAL DEFAULT 0,
    effective_fee_sum    REAL DEFAULT 0,
    stars_sum            REAL DEFAULT 0,
    tax_base             REAL DEFAULT 0,
    tax_15               REAL DEFAULT 0,
    net_profit           REAL DEFAULT 0,
    fetched_at           TEXT,
    raw_json             TEXT
);

CREATE TABLE monthly_realization_rows (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    month               TEXT NOT NULL,
    row_number          INTEGER,
    sku                 INTEGER,
    offer_id            TEXT,
    barcode             TEXT,
    item_name           TEXT,
    seller_price        REAL,
    sale_price          REAL,
    quantity            INTEGER,
    commission_ratio    REAL,
    gross_commission    REAL,
    bonus               REAL,
    coinvestment        REAL,
    logistics           REAL,
    total_held          REAL,
    effective_fee       REAL,
    stars               REAL,
    is_return           INTEGER DEFAULT 0,
    raw_json            TEXT
);
CREATE INDEX idx_mrr_month ON monthly_realization_rows(month);
CREATE INDEX idx_mrr_sku ON monthly_realization_rows(sku);
""")
con.commit()

print("\nНовая схема monthly_realization_rows:")
for r in con.execute("PRAGMA table_info(monthly_realization_rows)"):
    print(f"  {r[1]} {r[2]}")

con.close()
print("\n[OK] Готово. Запускай: py sync_monthly.py")
