"""
init_capital.py — создаёт таблицы для блока КАПИТАЛ.
"""
import sqlite3

con = sqlite3.connect("ozon.db")
con.executescript("""
-- Ручной ввод: сколько денег на счету
CREATE TABLE IF NOT EXISTS capital_input (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    update_date   TEXT NOT NULL,          -- YYYY-MM-DD
    on_account    REAL NOT NULL DEFAULT 0, -- ₽ на расчётном счету
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_ci_date ON capital_input(update_date);

-- План закупок: кому, сколько, когда
CREATE TABLE IF NOT EXISTS procurement_plan (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    due_date      TEXT NOT NULL,          -- когда платить
    supplier      TEXT,                    -- кому
    amount        REAL NOT NULL,           -- сколько ₽
    status        TEXT DEFAULT 'planned',  -- planned / paid / cancelled
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_pp_due ON procurement_plan(due_date);

-- Выплаты Ozon (из ЛК, вручную или из API если доступно)
CREATE TABLE IF NOT EXISTS payouts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    payout_date   TEXT NOT NULL,
    amount        REAL NOT NULL,          -- положительное = приход
    status        TEXT DEFAULT 'expected', -- expected / received
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_po_date ON payouts(payout_date);

-- План прибыли на месяц (для прогноза налога)
CREATE TABLE IF NOT EXISTS profit_plan (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month         TEXT NOT NULL UNIQUE,    -- YYYY-MM
    planned_profit REAL NOT NULL DEFAULT 0,
    note          TEXT
);
""")
con.commit()
con.close()
print("[OK] Таблицы capital_input, procurement_plan, payouts, profit_plan созданы")
