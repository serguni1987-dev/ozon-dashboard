"""
import_costs.py
Читает costs_template.csv (заполненный тобой) и сохраняет себестоимость в SQLite.
Добавляет колонку cost_price в products.
"""
import csv
import sqlite3
import os

DB = "ozon.db"
CSV = "costs_template.csv"


def main():
    if not os.path.exists(CSV):
        print(f"[ERROR] {CSV} не найден")
        return

    conn = sqlite3.connect(DB)

    # Добавим колонку, если её нет
    cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
    if "cost_price" not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN cost_price REAL")
        conn.commit()
        print("[OK] Добавлена колонка cost_price")

    # Читаем CSV
    updated = 0
    skipped = 0
    with open(CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            offer_id = (row.get("offer_id") or "").strip()
            cost_raw = (row.get("cost_price") or "").strip()

            if not offer_id or not cost_raw:
                skipped += 1
                continue

            # Парсим цену (убираем пробелы, запятые меняем на точки)
            cost_str = cost_raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")
            try:
                cost = float(cost_str)
            except ValueError:
                print(f"[WARN] Не парсится себестоимость у {offer_id}: '{cost_raw}'")
                skipped += 1
                continue

            cur = conn.execute(
                "UPDATE products SET cost_price = ? WHERE offer_id = ?",
                (cost, offer_id),
            )
            if cur.rowcount > 0:
                updated += 1
            else:
                print(f"[WARN] offer_id {offer_id} не найден в products")

    conn.commit()

    # Отчёт
    print(f"\n[OK] Обновлено: {updated}")
    print(f"[SKIP] Пропущено: {skipped}")

    cur = conn.execute("""
        SELECT COUNT(*) FROM products
        WHERE is_own=1 AND cost_price IS NOT NULL
    """)
    print(f"[OK] Себестоимость заполнена у {cur.fetchone()[0]} SKU (из 1204 своих)")

    # Топ-10 активных с себестоимостью
    print("\nТоп-10 активных SKU с себестоимостью:")
    cur = conn.execute("""
        SELECT p.offer_id, p.cost_price, SUM(s.revenue) as rev
        FROM sales_daily s
        JOIN products p ON p.sku = s.sku
        WHERE p.is_own=1 AND p.cost_price IS NOT NULL
        GROUP BY s.sku
        ORDER BY rev DESC
        LIMIT 10
    """)
    for oid, cost, rev in cur.fetchall():
        margin = (1 - cost / (rev / 1)) if rev else 0  # грубо
        print(f"  {oid:20s} себестоимость {cost:>8.0f} ₽, выручка {rev:>8.0f} ₽")

    conn.close()


if __name__ == "__main__":
    main()