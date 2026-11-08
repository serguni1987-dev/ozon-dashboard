"""Синхронизация costs_all.csv -> product_cost_history."""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from unitka import config

CSV_PATH = Path(r"C:\Users\sergu\Desktop\проект\costs_all.csv")


def load_costs():
    if not CSV_PATH.exists():
        print(f"[!] CSV не найден: {CSV_PATH}")
        return 0

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        rows = list(reader)

    now = datetime.now().isoformat(timespec="seconds")
    con = sqlite3.connect(str(config.DB_PATH))
    cur = con.cursor()

    added = updated = skipped = 0
    for row in rows:
        if len(row) < 6:
            skipped += 1
            continue
        try:
            sku = int(row[1])
            cost_price = float(row[4])
        except (ValueError, IndexError):
            skipped += 1
            continue
        if not cost_price:
            skipped += 1
            continue

        date_from = row[5].strip() or "2026-01-01"

        # Сначала пытаемся UPDATE по UNIQUE(sku, date_from)
        cur.execute(
            "UPDATE product_cost_history SET cost_price=?, source='csv', created_at=? "
            "WHERE sku=? AND date_from=?",
            (cost_price, now, sku, date_from))
        if cur.rowcount > 0:
            updated += cur.rowcount
            continue

        # Если такой пары нет — INSERT
        try:
            cur.execute(
                "INSERT INTO product_cost_history "
                "(sku, date_from, cost_price, source, created_at) "
                "VALUES (?, ?, ?, 'csv', ?)",
                (sku, date_from, cost_price, now))
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1

    con.commit()
    con.close()
    print(f"[OK] load_costs: добавлено={added}, обновлено={updated}, пропущено={skipped}")
    return added + updated


if __name__ == "__main__":
    load_costs()