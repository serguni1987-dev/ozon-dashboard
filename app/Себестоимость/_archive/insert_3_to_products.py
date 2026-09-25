"""insert_3_to_products.py — добавляет 3 SKU из costs_all.csv в products.
Берёт offer_id, sku, name прямо из CSV. is_own=1, cost_price из CSV.
"""
import csv
import sqlite3

CSV = "costs_all.csv"
targets = {"OBKR0241579020", "OBKR0251578016025", "MS01324"}

# ── 1. Из CSV ──
with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))

header = rows[0]
idx = {h: i for i, h in enumerate(header)}
print(f"Колонки: {header}")

found_in_csv = []
for r in rows[1:]:
    if len(r) > idx["offer_id"] and r[idx["offer_id"]].strip() in targets:
        found_in_csv.append({
            "offer_id": r[idx["offer_id"]].strip(),
            "sku": r[idx["sku"]].strip() if idx.get("sku") is not None else "",
            "name": r[idx["name"]] if idx.get("name") is not None else "",
            "cost_price": r[idx["cost_price"]].strip() if idx.get("cost_price") is not None else "",
        })
print(f"\nНайдено в CSV: {len(found_in_csv)}")

# ── 2. INSERT в products ──
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
inserted = 0
for row in found_in_csv:
    sku = row["sku"]
    if not sku:
        # Если в CSV sku пусто — ищем его в monthly_realization_rows по offer_id
        r = c.execute("SELECT DISTINCT sku FROM monthly_realization_rows WHERE offer_id = ?",
                      (row["offer_id"],)).fetchone()
        if not r:
            print(f"  [!] SKU не найден для {row['offer_id']}, пропуск")
            continue
        sku = str(r["sku"])
        print(f"  [i] SKU для {row['offer_id']} найден в monthly: {sku}")

    exists = c.execute("SELECT 1 FROM products WHERE sku = ?", (sku,)).fetchone()
    if exists:
        # Обновим cost_price, если задан
        if row["cost_price"]:
            c.execute("""
                UPDATE products SET cost_price = ?, is_own = 1,
                       cost_date = COALESCE(cost_date, '2026-01-01')
                WHERE sku = ?
            """, (row["cost_price"], sku))
            print(f"  [~] {row['offer_id']} уже есть — обновил cost_price={row['cost_price']}")
        else:
            print(f"  [i] {row['offer_id']} уже есть, cost_price пусто — пропуск")
        continue

    cost = row["cost_price"] or None
    c.execute("""
        INSERT INTO products (sku, offer_id, name, is_own, cost_price, cost_date,
                              first_seen, last_seen)
        VALUES (?, ?, ?, 1, ?, ?, '2026-01-01', '2026-01-01')
    """, (sku, row["offer_id"], row["name"] or "", cost,
          "2026-01-01" if cost else None))
    inserted += 1
    print(f"  [+] {row['offer_id']}  sku={sku}  cost={cost}")

c.commit()
print(f"\n[OK] Вставлено: {inserted}")

# ── 3. Проверка ──
print("\n=== Проверка ===")
for r in c.execute("""
    SELECT sku, offer_id, cost_price, is_own FROM products
    WHERE offer_id IN ('OBKR0241579020', 'OBKR0251578016025', 'MS01324')
"""):
    print(f"  {r['sku']:>12}  {r['offer_id']:<25}  cost={r['cost_price']}  is_own={r['is_own']}")

c.close()