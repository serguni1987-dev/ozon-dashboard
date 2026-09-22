import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

print("=" * 110)
print("ЧТО ПОМЕЧЕНО АРХИВНЫМ (is_own = 1)")
print("=" * 110)

rows = con.execute("""
    SELECT offer_id, name, category_l3, brand
    FROM products
    WHERE is_archived = 1 AND is_own = 1
    ORDER BY category_l3, offer_id
""").fetchall()

print(f"\nВсего: {len(rows)}\n")

# Группировка по категориям
by_cat = {}
for r in rows:
    cat = r["category_l3"] or "(без категории)"
    by_cat.setdefault(cat, []).append(r)

for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
    print(f"\n[{cat}]  — {len(items)} SKU")
    for r in items[:10]:
        name = (r["name"] or "")[:70]
        print(f"  {r['offer_id']:<20} {name}")
    if len(items) > 10:
        print(f"  ... и ещё {len(items) - 10}")

con.close()
