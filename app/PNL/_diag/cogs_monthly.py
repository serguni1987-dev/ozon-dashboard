# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path
from collections import defaultdict
import pandas as pd

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
XLSX = Path(r"C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx")

TARGETS = {"2026-01": 150126.0, "2026-02": 104592.0}

def detect_cols(df):
    lc = {c.lower().strip(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in lc: return lc[n]
    return (pick("sku","артикул","ozon sku","ozon_sku","offer_id"),
            pick("cost_price","цена","себестоимость","price","cost"),
            pick("date_from","дата","date","дата с","с","period"))

def load_xlsx_prices(path):
    df = pd.read_excel(path)
    sku_col, price_col, date_col = detect_cols(df)
    if not sku_col or not price_col:
        raise SystemExit("XLSX cols: " + str(list(df.columns)))
    df = df.dropna(subset=[sku_col, price_col]).copy()
    df[sku_col] = df[sku_col].astype(str).str.strip()
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df = df.dropna(subset=[price_col])
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values([sku_col, date_col], na_position="last")
    return df.groupby(sku_col)[price_col].last().to_dict()

def load_db_prices(conn):
    m = {}
    for r in conn.execute("SELECT sku, cost_price FROM product_cost_history WHERE cost_price IS NOT NULL ORDER BY sku, date_from DESC, id DESC"):
        m.setdefault(r["sku"], float(r["cost_price"]))
    for r in conn.execute("SELECT sku, cost_price FROM products WHERE cost_price IS NOT NULL"):
        m.setdefault(r["sku"], float(r["cost_price"]))
    return m

def load_all_months(conn):
    rows = conn.execute("SELECT CAST(month AS TEXT) AS month, sku, quantity, is_return FROM monthly_realization_rows").fetchall()
    by_month = defaultdict(list)
    for r in rows:
        by_month[str(r["month"])[:7]].append(r)
    return by_month

def calc(rows, prices):
    bq=0; buy=0.0; rq=0; ra=0.0; rs=0.0
    sold = {r["sku"] for r in rows if r["is_return"]==0}
    miss=set()
    for r in rows:
        c = prices.get(r["sku"]); q = r["quantity"] or 0
        if c is None:
            if q: miss.add(r["sku"])
            continue
        v = c*q
        if r["is_return"]==0: bq+=q; buy+=v
        elif r["is_return"]==1:
            rq+=q; ra+=v
            if r["sku"] in sold: rs+=v
    return {"bq":bq,"buy":buy,"rq":rq,"ra":ra,"rs":rs,"miss":miss}

def main():
    if not DB.exists(): raise SystemExit("No DB: " + str(DB))
    if not XLSX.exists(): raise SystemExit("No XLSX: " + str(XLSX))
    print("Reading XLSX...")
    xp = load_xlsx_prices(XLSX)
    print("  XLSX SKU:", len(xp))
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    dp = load_db_prices(conn)
    print("  DB SKU:  ", len(dp))
    bm = load_all_months(conn)
    months = sorted(bm.keys())
    print("\nMonths:", months)

    only_db = set(dp)-set(xp); only_x = set(xp)-set(dp)
    diff = [(s, dp[s], xp[s]) for s in (set(dp)&set(xp)) if abs(dp[s]-xp[s])>0.01]
    diff.sort(key=lambda x: abs(x[1]-x[2]), reverse=True)
    print("\nSKU only DB:", len(only_db), "| only XLSX:", len(only_x), "| diff price:", len(diff))
    for s,a,b in diff[:15]:
        print("  %-22s DB=%9.2f XLSX=%9.2f d=%+.2f" % (s,a,b,b-a))

    print("\n" + "="*110)
    print("%-8s | %6s | %10s | %6s | %10s | %11s | %12s | %10s | %8s | %8s | %8s" % (
        "month","buy_q","buy","ret_q","ret","buy-ret_all","buy-ret_sold","target","d(buy)","d(all)","d(sold)"))
    print("-"*110)
    for m in months:
        c = calc(bm[m], dp)
        t = TARGETS.get(m)
        ts = "%10.0f" % t if t else "%10s" % "-"
        db_ = "%+8.0f" % (c["buy"]-t) if t else "%8s" % "-"
        da_ = "%+8.0f" % (c["buy"]-c["ra"]-t) if t else "%8s" % "-"
        ds_ = "%+8.0f" % (c["buy"]-c["rs"]-t) if t else "%8s" % "-"
        print("%-8s | %6d | %10.0f | %6d | %10.0f | %11.0f | %12.0f | %s | %s | %s | %s" % (
            m, c["bq"], c["buy"], c["rq"], c["ra"], c["buy"]-c["ra"], c["buy"]-c["rs"], ts, db_, da_, ds_))

    print("\nRETURNS DETAIL:")
    for m in months:
        rets = [r for r in bm[m] if r["is_return"]==1]
        if not rets: continue
        print("\n", m, "-", len(rets), "returns")
        for r in rets:
            c = dp.get(r["sku"]); cs = "%.0f" % c if c else "-"
            print("   %-22s qty=%s cost=%8s sum=%8.0f" % (r["sku"], r["quantity"], cs, (c or 0)*(r["quantity"] or 0)))
    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()