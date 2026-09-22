"""
mark_brands.py
Помечает товары как "свои" / "чужие" в products.is_own.
Запуск: py mark_brands.py
"""
import sqlite3

DB_PATH = "ozon.db"

# Бренды, которые считаем СВОИМИ
OWN_BRANDS = [
    'VIVA - HOME TEXTILE',
    'VIVA HOME TEXTILE',
]


def main():
    conn = sqlite3.connect(DB_PATH)

    # Добавим колонку, если её ещё нет
    cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
    if 'is_own' not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN is_own INTEGER DEFAULT 0")
        print("[OK] Добавлена колонка is_own в products")
    conn.commit()

    # Сброс
    conn.execute("UPDATE products SET is_own = 0")

    # Проставить свои
    placeholders = ",".join("?" * len(OWN_BRANDS))
    conn.execute(
        f"UPDATE products SET is_own = 1 WHERE brand IN ({placeholders})",
        OWN_BRANDS,
    )
    conn.commit()

    # Отчёт
    cur = conn.execute("SELECT is_own, COUNT(*) FROM products GROUP BY is_own")
    for own, cnt in cur.fetchall():
        label = "СВОИ" if own else "ЧУЖИЕ"
        print(f"  {label}: {cnt} SKU")

    # Показать чужие бренды
    print("\nЧужие бренды в базе:")
    cur = conn.execute("""
        SELECT brand, COUNT(*) FROM products
        WHERE is_own = 0
        GROUP BY brand
        ORDER BY COUNT(*) DESC
    """)
    for brand, cnt in cur.fetchall():
        print(f"  {brand}: {cnt}")

    conn.close()


if __name__ == "__main__":
    main()