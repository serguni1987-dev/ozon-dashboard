import sqlite3
c = sqlite3.connect("ozon.db")
skus = ["OVL0492402602","OVL0312402602","OVS0032402602","VLR007E414025",
        "OCPR008E420020","VL007E4","OCPR0132416030","OCE017E4",
        "OCPR009E416030","OCPR002E418030"]
for oid in skus:
    row = c.execute("SELECT cost_price FROM products WHERE offer_id=?", (oid,)).fetchone()
    print(f"{oid:<18} cost_price = {row[0] if row else 'NOT FOUND'}")
