"""append_missing_to_costs.py — добавляет 16 SKU (продавались, но без
себестоимости) в costs_all.csv.
Формат: UTF-8-sig, разделитель ';'.
Колонки: offer_id;sku;name;category_l2;revenue_period;orders_period;cost_price;comment
"""
import csv
import sqlite3

CSV = "costs_all.csv"

# ── 1. Читаем ──
with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))

header = rows[0]
print(f"Колонки: {header}")
print(f"Строк: {len(rows)}")

idx_offer = header.index("offer_id")
offers_in_file = set()
for r in rows[1:]:
    if len(r) > idx_offer and r[idx_offer].strip():
        offers_in_file.add(r[idx_offer].strip())

# ── 2. 16 SKU из БД ──
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
missing = list(c.execute("""
    SELECT DISTINCT
        mr.sku,
        mr.offer_id,
        p.name,
        p.category_l2,
        SUM(mr.sale_price) AS revenue
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
    GROUP BY mr.sku
    ORDER BY revenue DESC
"""))
c.close()

print(f"\nSKU без себестоимости: {len(missing)}")

# ── 3. Добавляем ──
added = 0
for r in missing:
    offer = (r["offer_id"] or "").strip()
    if not offer:
        print(f"  [!] У SKU {r['sku']} пустой offer_id, пропускаю")
        continue
    if offer in offers_in_file:
        print(f"  {offer} — уже есть, пропускаю")
        continue
    new_row = [
        offer,
        str(r["sku"]),
        (r["name"] or "")[:200],
        r["category_l2"] or "",
        f"{r['revenue']:.1f}",
        "",
        "",        # cost_price — ЗАПОЛНИТЬ в Excel
        "",
    ]
    rows.append(new_row)
    added += 1
    print(f"  + {offer:<25} sku={r['sku']}")

# ── 4. Сохраняем ──
with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerows(rows)

print(f"\n[OK] Добавлено: {added}")
print(f"[OK] Итого строк: {len(rows)} (было {len(rows)-added})")
print()
print(f"Открываю Excel: start {CSV}")