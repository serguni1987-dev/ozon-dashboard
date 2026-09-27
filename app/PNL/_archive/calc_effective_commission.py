import os, json, requests, sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

H = {"Client-Id": os.getenv("OZON_CLIENT_ID"),
     "Api-Key": os.getenv("OZON_API_KEY"),
     "Content-Type": "application/json"}
URL = "https://api-seller.ozon.ru/v1/finance/accrual/by-day"

# 1. Собираем данные по каждому accrual с комиссией
records = []  # (date, sku, seller_price, sale_price, sale_commission, bonus, coinvestment)
d1 = datetime(2026, 9, 1)
d2 = datetime(2026, 9, 30)
d = d1
while d <= d2:
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
                c = p.get("commission")
                if not c:
                    continue
                sp  = float((c.get("seller_price") or {}).get("amount") or 0)
                slp = float((c.get("sale_price")   or {}).get("amount") or 0)
                cm  = float((c.get("sale_commission") or c.get("commission") or {}).get("amount") or 0)
                bn  = float((c.get("bonus")        or {}).get("amount") or 0)
                ci  = float((c.get("coinvestment") or {}).get("amount") or 0)
                records.append({
                    "date": ds, "sku": p.get("sku"),
                    "seller_price": sp, "sale_price": slp,
                    "commission": cm, "bonus": bn, "coinvestment": ci,
                })
        last_id = str(data.get("last_id") or "")
        if not last_id:
            break
    d += timedelta(days=1)

# 2. Итоги
n = len(records)
tot_sp   = sum(r["seller_price"] for r in records)
tot_slp  = sum(r["sale_price"] for r in records)
tot_comm = sum(r["commission"] for r in records)
tot_bonus = sum(r["bonus"] for r in records)
tot_coinv = sum(r["coinvestment"] for r in records)
eff = tot_comm + tot_bonus + tot_coinv

print("=" * 70)
print(f"Записей с комиссией: {n}")
print(f"seller_price:      {tot_sp:>12,.2f} ₽")
print(f"sale_price:        {tot_slp:>12,.2f} ₽")
print(f"скидка (sp - slp): {tot_sp - tot_slp:>12,.2f} ₽")
print(f"bonus:             {tot_bonus:>12,.2f} ₽")
print(f"coinvestment:      {tot_coinv:>12,.2f} ₽")
print(f"bonus+coinv:       {tot_bonus + tot_coinv:>12,.2f} ₽")
print(f"гросс-комиссия:    {tot_comm:>12,.2f} ₽")
print(f"эффект. комиссия:  {eff:>12,.2f} ₽")
if tot_sp:
    print(f"  % от seller_price: {eff / tot_sp * 100:>6.2f}%")
if tot_slp:
    print(f"  % от sale_price:   {eff / tot_slp * 100:>6.2f}%")
print("=" * 70)

# 3. Сопоставление с sales_daily
print("\nСОПОСТАВЛЕНИЕ С sales_daily (по дате и SKU):")
print("-" * 70)
con = sqlite3.connect("ozon.db")
cur = con.cursor()

matched = 0
for rec in records:
    row = cur.execute(
        "SELECT date, revenue, orders_units FROM sales_daily WHERE sku=? AND date=?",
        (rec["sku"], rec["date"])
    ).fetchone()
    if not row:
        continue
    rev = row[1]
    # Сравниваем: rev ближе к sale_price или seller_price?
    d_sale = abs(rev - rec["sale_price"])
    d_sel  = abs(rev - rec["seller_price"])
    match = "SALE" if d_sale < d_sel else "SELLER"
    if matched < 15:
        print(f"  {rec['date']} sku={rec['sku']:>12}  sales_daily.rev={rev:>10,.0f}  "
              f"sale={rec['sale_price']:>10,.0f}  seller={rec['seller_price']:>10,.0f}  → {match}")
    matched += 1

print(f"\n  Всего сопоставлено записей: {matched} из {n}")

# 4. Агрегируем по совпадению
sum_rev = 0.0; sum_sale = 0.0; sum_seller = 0.0; cnt_sale = 0; cnt_seller = 0
for rec in records:
    row = cur.execute(
        "SELECT revenue FROM sales_daily WHERE sku=? AND date=?",
        (rec["sku"], rec["date"])
    ).fetchone()
    if not row:
        continue
    rev = row[0]
    sum_rev += rev
    sum_sale += rec["sale_price"]
    sum_seller += rec["seller_price"]
    if abs(rev - rec["sale_price"]) < abs(rev - rec["seller_price"]):
        cnt_sale += 1
    else:
        cnt_seller += 1

print(f"\n  Сумма revenue (совпавшие): {sum_rev:>12,.2f} ₽")
print(f"  Сумма sale_price:          {sum_sale:>12,.2f} ₽")
print(f"  Сумма seller_price:        {sum_seller:>12,.2f} ₽")
print(f"  Совпадений с sale_price:   {cnt_sale}")
print(f"  Совпадений с seller_price: {cnt_seller}")
con.close()
