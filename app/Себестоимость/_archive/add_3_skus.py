"""add_3_skus.py — добавляет 3 SKU (есть в отчёте реализации, нет в products):
1. INSERT в products (is_own=1)
2. Дописывает их в costs_all.csv (cost_price пустой)
3. Показывает итоговую строку для Excel
"""
import csv
import sqlite3
from datetime import datetime

c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

# ── 1. Найти 3 SKU ──
print("=== Ищу 3 SKU в monthly_realization_rows ===")
rows = list(c.execute("""
    SELECT DISTINCT
        mr.sku,
        mr.offer_id,
        MIN(mr.month) AS first_month,
        SUM(mr.quantity) AS qty,
        SUM(mr.sale_price) AS slp
    FROM monthly_realization_rows mr
    WHERE mr.offer_id IN ('OBKR0241579020', 'OBKR0251578016025', 'MS01324')
    GROUP BY mr.sku
"""))

if not rows:
    print("[!] Ничего не найдено")
    c.close()
    raise SystemExit

print(f"Найдено: {len(rows)}")

# ── 2. INSERT в products ──
inserted = 0
for r in rows:
    exists = c.execute("SELECT 1 FROM products WHERE sku = ?", (r["sku"],)).fetchone()
    if exists:
        print(f"  {r['sku']} уже есть в products, пропускаю INSERT")
        continue
    c.execute("""
        INSERT INTO products
            (sku, offer_id, name, is_own, cost_price, cost_date, first_seen, last_seen)
        VALUES (?, ?, ?, 1, NULL, NULL, ?, ?)
    """, (
        r["sku"],
        r["offer_id"],
        f"SKU {r['offer_id']} — заполнить название",
        r["first_month"] + "-01",
        datetime.now().strftime("%Y-%m-%d"),
    ))
    inserted += 1
    print(f"  [+] добавлен в products: sku={r['sku']} offer_id={r['offer_id']} "
          f"qty={r['qty']} slp={r['slp']:.2f}")

c.commit()
print(f"\n[OK] Вставлено в products: {inserted}")

# ── 3. Дописать в costs_all.csv ──
CSV = "costs_all.csv"
with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows_csv = list(csv.reader(f, delimiter=";"))

header = rows_csv[0]
idx_offer = header.index("offer_id")
offers_in_csv = {r[idx_offer].strip() for r in rows_csv[1:] if len(r) > idx_offer}

added = 0
for r in rows:
    offer = r["offer_id"]
    if offer in offers_in_csv:
        print(f"  {offer} уже в costs_all.csv, пропускаю")
        continue
    new_row = [
        offer,
        str(r["sku"]),
        f"SKU {offer}",       # name
        "",                    # category_l2
        f"{r['slp']:.1f}",    # revenue_period
        str(r["qty"]),        # orders_period
        "",                    # cost_price — ЗАПОЛНИТЬ
        "",
    ]
    rows_csv.append(new_row)
    added += 1
    print(f"  [+] в costs_all.csv: {offer}")

with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerows(rows_csv)

print(f"\n[OK] Добавлено в costs_all.csv: {added}")
print(f"[OK] Всего строк: {len(rows_csv)} (было {len(rows_csv)-added})")

# ── 4. Итог ──
print()
print("=== Эти 3 SKU для заполнения в Excel ===")
for r in rows:
    print(f"  {r['offer_id']:<25}  qty={r['qty']}  slp={r['slp']:.2f}")

c.close()
print()
print(f"Открываю Excel: start {CSV}")