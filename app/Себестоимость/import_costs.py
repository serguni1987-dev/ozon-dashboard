"""
import_costs.py — читает проект/costs_all.csv.
Формат: offer_id;sku;name;category_l2;cost_price;date_from;cost_price_new;date_from_new
Применяет ТОЛЬКО колонки 7-8 (новая цена): если заполнены →
добавляет в product_cost_history + обновляет products.
"""
import csv
import sqlite3
import os
from datetime import date

COST_DIR = os.path.dirname(os.path.abspath(__file__))       # app/Себестоимость
APP_DIR = os.path.dirname(COST_DIR)                        # app
PROJECT_DIR = os.path.dirname(APP_DIR)                     # проект
DB = os.path.join(APP_DIR, "ozon.db")
CSV = os.path.join(PROJECT_DIR, "costs_all.csv")


def parse_date(s):
    """Принимает '2026-01-01' и '01.01.2026'."""
    s = (s or "").strip()
    if not s:
        return None
    if "-" in s:
        return s
    if "." in s:
        parts = s.split(".")
        if len(parts) == 3:
            d, m, y = parts
            return f"{y}-{m}-{d}"
    return None


def parse_cost(s):
    s = (s or "").strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    if not os.path.exists(CSV):
        print(f"[ERROR] {CSV} не найден")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_cost_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku INTEGER NOT NULL,
            date_from TEXT NOT NULL,
            cost_price REAL NOT NULL,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sku, date_from)
        )
    """)
    conn.commit()

    today = date.today().isoformat()
    updated = 0
    new_history = 0
    skipped = 0
    not_found = 0

    with open(CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            offer_id = (row.get("offer_id") or "").strip()
            if not offer_id:
                skipped += 1
                continue

            # Только новая цена
            new_cost_raw = (row.get("cost_price_new") or "").strip()
            new_date_raw = (row.get("date_from_new") or "").strip()

            if not new_cost_raw:
                continue

            cost = parse_cost(new_cost_raw)
            if cost is None:
                print(f"[WARN] Не парсится цена у {offer_id}: '{new_cost_raw}'")
                skipped += 1
                continue

            date_from = parse_date(new_date_raw) or today

            r = conn.execute("SELECT sku FROM products WHERE offer_id = ?",
                             (offer_id,)).fetchone()
            if not r:
                not_found += 1
                continue
            sku = r["sku"]

            conn.execute("UPDATE products SET cost_price = ?, cost_date = ? WHERE sku = ?",
                         (cost, date_from, sku))
            updated += 1

            conn.execute("""
                INSERT OR REPLACE INTO product_cost_history
                    (sku, date_from, cost_price, source)
                VALUES (?, ?, ?, 'import')
            """, (sku, date_from, cost))
            new_history += 1

    conn.commit()

    print(f"\n[OK] Обновлено products: {updated}")
    print(f"[OK] Добавлено в историю: {new_history}")
    print(f"[SKIP] Пропущено: {skipped}")
    if not_found:
        print(f"[WARN] offer_id не найден: {not_found}")

    n_own = conn.execute("SELECT COUNT(*) FROM products WHERE is_own=1").fetchone()[0]
    n_cost = conn.execute("""
        SELECT COUNT(*) FROM products WHERE is_own=1 AND cost_price > 0
    """).fetchone()[0]
    print(f"\n[OK] Себестоимость у {n_cost} из {n_own} SKU")

    n_hist = conn.execute("SELECT COUNT(*) FROM product_cost_history").fetchone()[0]
    print(f"[OK] Всего записей в истории: {n_hist}")

    print("\nИстория по датам:")
    for r in conn.execute("""
        SELECT date_from, source, COUNT(*) AS n
        FROM product_cost_history
        GROUP BY date_from, source
        ORDER BY date_from DESC
        LIMIT 10
    """):
        print(f"  {r['date_from']}  {r['source']:<12}  {r['n']} SKU")

    conn.close()


if __name__ == "__main__":
    main()