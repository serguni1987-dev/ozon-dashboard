import sqlite3
import pandas as pd

CSV = r'C:\Users\sergu\Desktop\проект\costs_all.csv'
DB  = r'C:\Users\sergu\Desktop\проект\app\ozon.db'

csv = pd.read_csv(CSV, sep=';', dtype=str)
csv['sku'] = pd.to_numeric(csv['sku'], errors='coerce')

conn = sqlite3.connect(DB)
db_skus = set(r[0] for r in conn.execute("SELECT DISTINCT sku FROM product_cost_history"))

csv_skus = set(csv['sku'].dropna().astype(int))
missing = csv_skus - db_skus
extra   = db_skus - csv_skus

print(f'CSV SKU:  {len(csv_skus)}')
print(f'БД SKU:   {len(db_skus)}')
print(f'Нет в БД: {len(missing)}')
print(f'Лишних в БД: {len(extra)}')

print('\n=== 20 примеров SKU из CSV, которых нет в БД ===')
miss_df = csv[csv['sku'].isin(missing)][['offer_id','sku','name','cost_price']]
print(miss_df.head(20).to_string(index=False))

print('\n=== Продавались ли эти SKU в январе/феврале? ===')
jan_feb = set()
for sku, m in conn.execute("""
    SELECT DISTINCT sku, month FROM monthly_realization_rows
    WHERE month IN ('2026-01','2026-02')
"""):
    jan_feb.add((sku, m))

missing_critical = [(s, m) for s, m in jan_feb if s in missing]
print(f'Продаж в янв/фев по SKU без цены: {len(missing_critical)}')
for s, m in sorted(missing_critical):
    offer = csv.loc[csv['sku']==s, 'offer_id'].iloc[0] if s in csv_skus else '?'
    cost = csv.loc[csv['sku']==s, 'cost_price'].iloc[0] if s in csv_skus else '?'
    print(f'  sku={s}, offer={offer}, cost={cost}, month={m}')

conn.close()