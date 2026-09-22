import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

print("=== OCE013E4 и другие изменённые SKU ===")
for oid in ["OCE013E4", "OCPR0022418030", "OCER002E418030",
            "OCER005E418030", "OCER013E416030", "OCER013E418030"]:
    r = con.execute(
        "SELECT offer_id, price, old_price, min_price, marketing_price FROM current_prices WHERE offer_id = ?",
        (oid,)
    ).fetchone()
    if r:
        print(f"  {r['offer_id']:<18} price={r['price']} old={r['old_price']} min={r['min_price']} market={r['marketing_price']}")
    else:
        print(f"  {oid}: НЕ НАЙДЕН в current_prices")

con.close()
