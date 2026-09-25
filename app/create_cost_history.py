"""create_cost_history.py — создаёт product_cost_history и заполняет
текущими ценами из products.cost_price с датой 2026-01-01.
"""
import sqlite3

DB = "ozon.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# ── 1. Создать таблицу ──
print("=== Создаю product_cost_history ===")
c.execute("""
    CREATE TABLE IF NOT EXISTS product_cost_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sku         INTEGER NOT NULL,
        date_from   TEXT NOT NULL,
        cost_price  REAL NOT NULL,
        source      TEXT DEFAULT 'manual',
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(sku, date_from)
    )
""")
c.execute("""
    CREATE INDEX IF NOT EXISTS idx_cost_history_sku_date
    ON product_cost_history(sku, date_from)
""")
c.commit()
print("[OK] Таблица создана")

# ── 2. Заполнить из products ──
print()
print("=== Заполняю из products.cost_price ===")
before = c.execute("SELECT COUNT(*) FROM product_cost_history").fetchone()[0]
print(f"  Уже было записей: {before}")

# Сколько SKU с ценой
n = c.execute("""
    SELECT COUNT(*) FROM products
    WHERE cost_price > 0 AND is_own = 1
""").fetchone()[0]
print(f"  SKU со стоимостью (is_own=1): {n}")

# Заполняем
c.execute("""
    INSERT OR IGNORE INTO product_cost_history (sku, date_from, cost_price, source)
    SELECT sku, '2026-01-01', cost_price, 'migration'
    FROM products
    WHERE cost_price > 0 AND is_own = 1
""")
c.commit()

after = c.execute("SELECT COUNT(*) FROM product_cost_history").fetchone()[0]
print(f"  Стало записей: {after}  (+{after-before})")

# ── 3. Проверка ──
print()
print("=== Контрольная проверка ===")
for r in c.execute("""
    SELECT date_from, source, COUNT(*) AS n
    FROM product_cost_history
    GROUP BY date_from, source
    ORDER BY date_from
"""):
    print(f"  {r['date_from']}  source={r['source']:<12}  {r['n']} SKU")

print()
print("=== Топ-5 SKU по истории ===")
for r in c.execute("""
    SELECT sku, date_from, cost_price, source
    FROM product_cost_history
    ORDER BY sku
    LIMIT 5
"""):
    print(f"  {r['sku']:>12}  {r['date_from']}  {r['cost_price']:>10.2f}  {r['source']}")

c.close()
print()
print("[OK] Готово")