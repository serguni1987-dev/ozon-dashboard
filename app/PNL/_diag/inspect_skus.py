# -*- coding: utf-8 -*-
"""inspect_skus.py — что за SKU в XLSX, БД, realization, где матчинг ломается."""
import sqlite3
from pathlib import Path
import pandas as pd

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
XLSX = Path(r"C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=== monthly_realization_rows ===")
cols = [d[0] for d in conn.execute("SELECT * FROM monthly_realization_rows LIMIT 0").description]
print("cols:", cols)
print("distinct sku (10):")
for r in conn.execute("SELECT DISTINCT sku FROM monthly_realization_rows LIMIT 10"):
    print("  ", repr(r["sku"]))
print("distinct offer_id (10):")
for r in conn.execute("SELECT DISTINCT offer_id FROM monthly_realization_rows LIMIT 10"):
    print("  ", repr(r["offer_id"]))

print("\n=== product_cost_history ===")
cols = [d[0] for d in conn.execute("SELECT * FROM product_cost_history LIMIT 0").description]
print("cols:", cols)
print("distinct sku (10):")
for r in conn.execute("SELECT DISTINCT sku FROM product_cost_history LIMIT 10"):
    print("  ", repr(r["sku"]))

print("\n=== products ===")
cols = [d[0] for d in conn.execute("SELECT * FROM products LIMIT 0").description]
print("cols:", cols)
for r in conn.execute("SELECT * FROM products LIMIT 3"):
    print("  ", dict(r))

print("\n=== OVERLAP ===")
mr_skus = {r["sku"] for r in conn.execute("SELECT DISTINCT sku FROM monthly_realization_rows")}
mr_offer = {r["offer_id"] for r in conn.execute("SELECT DISTINCT offer_id FROM monthly_realization_rows WHERE offer_id IS NOT NULL AND offer_id != ''")}
ch_skus = {r["sku"] for r in conn.execute("SELECT DISTINCT sku FROM product_cost_history")}
pr_skus = {r["sku"] for r in conn.execute("SELECT DISTINCT sku FROM products")}
pr_offer = {r["offer_id"] for r in conn.execute("SELECT DISTINCT offer_id FROM products WHERE offer_id IS NOT NULL AND offer_id != ''")}
print(f"mr.sku:      {len(mr_skus)}")
print(f"mr.offer_id: {len(mr_offer)}")
print(f"ch.sku:      {len(ch_skus)}")
print(f"pr.sku:      {len(pr_skus)}")
print(f"pr.offer_id: {len(pr_offer)}")
print(f"mr.sku ∩ ch.sku:       {len(mr_skus & ch_skus)}")
print(f"mr.offer_id ∩ ch.sku:  {len(mr_offer & ch_skus)}")
print(f"mr.sku ∩ pr.sku:       {len(mr_skus & pr_skus)}")
print(f"mr.offer_id ∩ pr.offer_id: {len(mr_offer & pr_offer)}")

print("\n=== XLSX ===")
df = pd.read_excel(XLSX)
print("shape:", df.shape)
print("columns:")
for c in df.columns:
    sample = df[c].dropna().head(3).tolist()
    print(f"  {c!r}: {sample}")

# Первые 5 строк XLSX в сыром виде
print("\nHead 5:")
print(df.head(5).to_string())

conn.close()
print("\nDone.")