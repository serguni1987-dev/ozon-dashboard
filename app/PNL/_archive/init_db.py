"""
init_db.py
Создаёт SQLite-базу ozon.db из db/schema.sql.
Запуск один раз. При повторном запуске таблицы не пересоздаются (IF NOT EXISTS).
"""
import os
import sqlite3
import sys

DB_PATH = "ozon.db"
SCHEMA_PATH = os.path.join("db", "schema.sql")


def main():
    if not os.path.exists(SCHEMA_PATH):
        print(f"[ERROR] Файл схемы не найден: {SCHEMA_PATH}")
        sys.exit(1)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

    if exists:
        print(f"[OK] База обновлена: {DB_PATH}")
    else:
        print(f"[OK] База создана: {DB_PATH}")

    # Покажем, какие таблицы внутри
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    conn.close()

    print(f"[OK] Таблицы: {', '.join(tables)}")


if __name__ == "__main__":
    main()