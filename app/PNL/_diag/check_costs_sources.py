import sqlite3, os
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

# Есть ли таблица с историей себестоимости?
print("Таблицы в БД:")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    if 'cost' in r['name'].lower() or 'price' in r['name'].lower() or 'sebes' in r['name'].lower():
        print(f"  {r['name']}")

# Все колонки products
print("\nКолонки products:")
print(" ", [r[1] for r in c.execute("PRAGMA table_info(products)")])

# Смотры cost_price этих 16 SKU — может частично заполнено
missing_skus = [1879636339, 1281819166, 2288681486, 1591552350, 1609915178,
                2288693078, 1281720312, 1879635959, 1879635938, 1598572996,
                1879636428, 1267412652, 1616350111, 1331069847, 1610041376, 1609915213]
q = ",".join(map(str, missing_skus))
print("\nЭти 16 SKU в products:")
for r in c.execute(f"SELECT sku, offer_id, name, cost_price, is_own FROM products WHERE sku IN ({q})"):
    name = (r['name'] or '')[:40]
    print(f"  {r['sku']:>12} | cost_price={r['cost_price']} | is_own={r['is_own']} | {r['offer_id']} | {name}")

# Файлы в downloads / Себестоимость
print("\nФайлы в папках:")
for folder in ["Себестоимость", "../Себестоимость", "../downloads"]:
    p = folder if os.path.isabs(folder) else folder
    if os.path.isdir(p):
        print(f"  {p}:")
        for f in os.listdir(p)[:20]:
            print(f"    {f}")

c.close()