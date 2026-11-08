import sqlite3, json
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("=== raw_json для 5 проблемных заказов ===")
for r in con.execute("""
    SELECT posting_number, date, sku, seller_price, raw_json
    FROM realization_daily
    WHERE posting_number IN (
        '50313579-0458-1','76421118-0054-1','50438345-0435-1',
        '0115723697-0071-1','25456394-0146-1'
    )
    LIMIT 5
"""):
    print(f"\n=== {r['posting_number']} | {r['date']} | sku={r['sku']} ===")
    try:
        d = json.loads(r["raw_json"])
        # в raw_json лежит prod (products[i]), а нам нужен весь acc
        # посмотрим что есть
        for k in ("sku","quantity","commission","delivery","posting_number"):
            if k in d:
                print(f"  {k}: {d[k]}")
    except Exception as e:
        print(f"  parse err: {e}")

print("\n=== Первые 3 строки raw_json целиком ===")
for r in con.execute("""
    SELECT posting_number, raw_json FROM realization_daily
    WHERE posting_number = '50313579-0458-1' LIMIT 1
"""):
    print(f"posting_number в БД: {r['posting_number']}")
    print(f"raw_json (первые 800): {r['raw_json'][:800]}")