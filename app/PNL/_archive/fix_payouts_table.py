"""
fix_payouts_table.py — удаляет старую таблицу payouts и создаёт с правильной схемой.
"""
import sqlite3

con = sqlite3.connect("ozon.db")

# Проверим текущую схему
print("Старая схема payouts:")
for r in con.execute("PRAGMA table_info(payouts)"):
    print(f"  {r[1]} {r[2]}")

# Удаляем старую
con.execute("DROP TABLE IF EXISTS payouts")
con.commit()
print("\n[OK] Старая таблица payouts удалена")

# Создаём новую
con.executescript("""
CREATE TABLE payouts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period_begin      TEXT NOT NULL,
    period_end        TEXT NOT NULL,
    orders_amount     REAL,
    returns_amount    REAL,
    commission_amount REAL,
    services_amount   REAL,
    delivery_amount   REAL,
    total_amount      REAL,
    status            TEXT DEFAULT 'expected',
    fetched_at        TEXT
);
CREATE UNIQUE INDEX idx_po_period ON payouts(period_begin, period_end);
""")
con.commit()

print("\nНовая схема payouts:")
for r in con.execute("PRAGMA table_info(payouts)"):
    print(f"  {r[1]} {r[2]}")

con.close()
print("\n[OK] Готово. Запускай: py fetch_payouts.py")
