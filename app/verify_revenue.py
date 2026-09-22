import os, requests, sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

H = {"Client-Id": os.getenv("OZON_CLIENT_ID"),
     "Api-Key": os.getenv("OZON_API_KEY"),
     "Content-Type": "application/json"}
URL = "https://api-seller.ozon.ru/v1/finance/accrual/by-day"

TARGET_SKU = 1605108599  # OCE013E4

tot_sale = 0.0; tot_seller = 0.0; n = 0
d = datetime(2026, 9, 1)
while d <= datetime(2026, 9, 30):
    ds = d.strftime("%Y-%m-%d")
    last_id = ""
    while True:
        r = requests.post(URL, headers=H, json={"date": ds, "last_id": last_id}, timeout=60)
        data = r.json()
        rows = data.get("accruals") or []
        if not rows:
            break
        for acc in rows:
            for p in (acc.get("posting") or {}).get("products") or []:
                if p.get("sku") != TARGET_SKU:
                    continue
                c = p.get("commission")
                if not c:
                    continue
                tot_sale   += float((c.get("sale_price")   or {}).get("amount") or 0)
                tot_seller += float((c.get("seller_price") or {}).get("amount") or 0)
                n += 1
        last_id = str(data.get("last_id") or "")
        if not last_id:
            break
    d += timedelta(days=1)

con = sqlite3.connect("ozon.db")
rev_total = con.execute(
    "SELECT SUM(revenue), SUM(orders_units) FROM sales_daily WHERE sku=?", (TARGET_SKU,)
).fetchone()
con.close()

print(f"SKU {TARGET_SKU} (OCE013E4)")
print(f"  Записей с commission:          {n}")
print(f"  Сумма sale_price:              {tot_sale:>12,.2f} ₽")
print(f"  Сумма seller_price:            {tot_seller:>12,.2f} ₽")
print(f"  sales_daily.revenue (SUM):     {rev_total[0]:>12,.2f} ₽")
print(f"  sales_daily.orders_units:      {rev_total[1]}")
