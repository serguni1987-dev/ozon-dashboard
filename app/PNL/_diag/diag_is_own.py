import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Что в поле brand у 16 SKU ===")
targets = (1879636339, 1281819166, 2288681486, 1591552350, 1609915178,
           2288693078, 1281720312, 1879635959, 1879635938, 1598572996,
           1879636428, 1267412652, 1616350111, 1331069847, 1610041376, 1609915213)
q = ",".join(map(str, targets))
for r in c.execute(f"""
    SELECT sku, offer_id, brand, name
    FROM products WHERE sku IN ({q})
    ORDER BY sku
"""):
    name = (r['name'] or '')[:40]
    print(f"  sku={r['sku']:>12}  brand={r['brand']!r:<20}  {name}")

print()
print("=== ТОП брендов у is_own=1 ===")
for r in c.execute("""
    SELECT brand, COUNT(*) AS n
    FROM products WHERE is_own = 1
    GROUP BY brand ORDER BY n DESC LIMIT 15
"""):
    print(f"  {r['brand']!r}: {r['n']}")