"""
import_costs_from_sebest.py - v5: автоопределение кодировки И разделителя.
"""
import csv
import os
import re
import sqlite3
from datetime import datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
ROOT = os.path.dirname(APP_DIR)
CSV = os.path.join(ROOT, "Себестоимость", "costs_all.csv")


def read_csv_auto(path):
    """Читает CSV/TSV с автоопределением кодировки и разделителя."""
    encodings = ["utf-8-sig", "utf-8", "cp1251"]
    delimiters = [";", "\t", ","]

    for enc in encodings:
        for delim in delimiters:
            try:
                with open(path, encoding=enc, newline="") as f:
                    reader = csv.DictReader(f, delimiter=delim)
                    rows = list(reader)
                    if rows and ("Артикул" in rows[0] or "SKU" in rows[0]):
                        print(f"  Кодировка: {enc}")
                        print(f"  Разделитель: {repr(delim)}")
                        return rows
            except (UnicodeDecodeError, UnicodeError, csv.Error):
                continue
    raise ValueError("Не удалось прочитать файл")


def to_money(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s in {"-", "—", "None"}:
        return None
    s = s.replace("₽", "").replace("\u00a0", "").replace(" ", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        f = float(s)
        return f if f > 0 else None
    except ValueError:
        return None


def to_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    try:
        d = datetime(1899, 12, 30) + timedelta(days=int(float(s)))
        return d.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


print("Читаем:", CSV)
rows = read_csv_auto(CSV)
print("Прочитано строк:", len(rows))
print("Колонки:", list(rows[0].keys()))

con = sqlite3.connect(DB)
cur = con.cursor()
updated = skipped = not_found = 0
changes = []
today = datetime.now().strftime("%Y-%m-%d")

for r in rows:
    offer_id = (r.get("Артикул") or r.get("offer_id") or "").strip()
    sku = (r.get("SKU") or r.get("sku") or "").strip()
    cost = to_money(r.get("Себестоимость") or r.get("cost_price"))
    cost_date = to_date(r.get("Дата себестоимости") or r.get("cost_date")) or today

    if cost is None:
        skipped += 1
        continue

    old = cur.execute(
        "SELECT cost_price FROM products WHERE offer_id = ?", (offer_id,)
    ).fetchone()
    old_cost = old[0] if old else None

    found = False
    if offer_id:
        cur.execute("""
            UPDATE products SET cost_price = ?, cost_date = ?
            WHERE offer_id = ?
        """, (cost, cost_date, offer_id))
        if cur.rowcount > 0:
            updated += 1
            found = True
    if not found and sku:
        try:
            cur.execute("""
                UPDATE products SET cost_price = ?, cost_date = ?
                WHERE sku = ?
            """, (cost, cost_date, int(float(sku))))
            if cur.rowcount > 0:
                updated += 1
                found = True
        except ValueError:
            pass
    if not found:
        not_found += 1

    if old_cost and abs(old_cost - cost) > 0.01:
        changes.append((offer_id, old_cost, cost))

con.commit()

total = cur.execute("SELECT COUNT(*) FROM products WHERE is_own = 1").fetchone()[0]
with_cost = cur.execute("""
    SELECT COUNT(*) FROM products
    WHERE is_own = 1 AND cost_price > 0
""").fetchone()[0]

print()
print("  Обновлено:", updated)
print("  Пропущено (нет цены):", skipped)
print("  Не найдено:", not_found)
print()
print("  Всего своих SKU:", total)
print("  С себестоимостью:", with_cost)
print("  Без себестоимости:", total - with_cost)

if changes:
    print()
    print(f"  Изменения цен ({len(changes)}):")
    for oid, old, new in changes[:20]:
        print(f"    {oid:<25} {old:>10,.2f} -> {new:>10,.2f}")

con.close()
