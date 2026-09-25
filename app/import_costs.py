"""
import_costs.py
Читает проект/costs_all.csv и сохраняет себестоимость в SQLite + историю.
Формат CSV: offer_id;sku;name;category_l2;cost_price;date_from;comment
- Если date_from пусто → сегодняшняя дата
- Если цена новая (отличается от последней в истории) → новая запись в product_cost_history
- Всегда обновляет products.cost_price на актуальную
"""
import csv
import sqlite3
import os
from datetime import date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
DB = os.path.join(APP_DIR, "ozon.db")
CSV = os.path.join(PROJECT_DIR, "costs_all.csv")


def main():
    if not os.path.exists(CSV):
        print(f"[ERROR] {CSV} не найден")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Создаём таблицу истории, если её нет
    conn.execute("""
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
    conn.commit()

    today = date.today().isoformat()

    updated = 0          # обновили products.cost_price
    new_history = 0      # добавили запись в историю
    skipped = 0          # пустой cost_price или ошибка парсинга
    not_found = 0        # offer_id нет в products

    with open(CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            offer_id = (row.get("offer_id") or "").strip()
            cost_raw = (row.get("cost_price") or "").strip()
            date_from = (row.get("date_from") or "").strip() or today

            if not offer_id or not cost_raw:
                skipped += 1
                continue

            # Парсим цену
            cost_str = cost_raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")
            try:
                cost = float(cost_str)
            except ValueError:
                print(f"[WARN] Не парсится себестоимость у {offer_id}: '{cost_raw}'")
                skipped += 1
                continue

            # Найти sku в products
            r = conn.execute("SELECT sku, cost_price FROM products WHERE offer_id = ?",
                             (offer_id,)).fetchone()
            if not r:
                not_found += 1
                continue
            sku = r["sku"]
            old_cost = r["cost_price"]

            # Обновить products.cost_price
            conn.execute("UPDATE products SET cost_price = ?, cost_date = ? WHERE sku = ?",
                         (cost, date_from, sku))
            updated += 1

            # История: добавить, если такого date_from+sku нет, или цена изменилась
            existing = conn.execute("""
                SELECT cost_price FROM product_cost_history
                WHERE sku = ? AND date_from = ?
            """, (sku, date_from)).fetchone()

            if not existing:
                conn.execute("""
                    INSERT INTO product_cost_history (sku, date_from, cost_price, source)
                    VALUES (?, ?, ?, 'import')
                """, (sku, date_from, cost))
                new_history += 1

    conn.commit()

    # ── Отчёт ──
    print(f"\n[OK] Обновлено products: {updated}")
    print(f"[OK] Добавлено в историю: {new_history}")
    print(f"[SKIP] Пропущено (пусто/ошибка): {skipped}")
    if not_found:
        print(f"[WARN] offer_id не найден в products: {not_found}")

    n_own = conn.execute("SELECT COUNT(*) FROM products WHERE is_own=1").fetchone()[0]
    n_cost = conn.execute("""
        SELECT COUNT(*) FROM products WHERE is_own=1 AND cost_price IS NOT NULL AND cost_price > 0
    """).fetchone()[0]
    print(f"\n[OK] Себестоимость у {n_cost} из {n_own} своих SKU")

    n_hist = conn.execute("SELECT COUNT(*) FROM product_cost_history").fetchone()[0]
    print(f"[OK] Всего записей в истории: {n_hist}")

    # Историю по датам
    print("\nИстория по датам:")
    for r in conn.execute("""
        SELECT date_from, source, COUNT(*) AS n
        FROM product_cost_history
        GROUP BY date_from, source
        ORDER BY date_from DESC
        LIMIT 10
    """):
        print(f"  {r['date_from']}  {r['source']:<12}  {r['n']} SKU")

    # Топ-5 активных
    print("\nТоп-5 активных SKU:")
    for r in conn.execute("""
        SELECT p.offer_id, p.cost_price, SUM(s.revenue) AS rev
        FROM sales_daily s
        JOIN products p ON p.sku = s.sku
        WHERE p.is_own=1 AND p.cost_price > 0
        GROUP BY s.sku
        ORDER BY rev DESC
        LIMIT 5
    """):
        print(f"  {r['offer_id']:20s}  себест. {r['cost_price']:>8.0f} ₽,  выручка {r['rev']:>9.0f} ₽")

    conn.close()


if __name__ == "__main__":
    main()