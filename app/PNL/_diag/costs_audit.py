import os, sqlite3
import pandas as pd

CSV  = r'C:\Users\sergu\Desktop\проект\costs_all.csv'
XLSX = r'C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx'
DB   = r'C:\Users\sergu\Desktop\проект\app\ozon.db'

# ---------- 1. CSV ----------
print('=== 1. costs_all.csv ===')
csv = pd.read_csv(CSV, sep=';', dtype=str)
print(f'Строк: {len(csv)}')
print(f'Колонки: {list(csv.columns)}')
print(f'Уникальных offer_id: {csv["offer_id"].nunique() if "offer_id" in csv.columns else "нет"}')
print(f'Уникальных sku: {csv["sku"].nunique() if "sku" in csv.columns else "нет"}')
print('\nПервые 3 строки:')
print(csv.head(3).to_string(index=False))

# ---------- 2. БД ----------
print('\n=== 2. product_cost_history (БД) ===')
conn = sqlite3.connect(DB)
total = conn.execute("SELECT COUNT(*) FROM product_cost_history").fetchone()[0]
uniq_sku = conn.execute("SELECT COUNT(DISTINCT sku) FROM product_cost_history").fetchone()[0]
print(f'Всего строк: {total}')
print(f'Уникальных sku: {uniq_sku}')
print(f'Дублей (строк − sku): {total - uniq_sku}')

dupes = conn.execute("""
    SELECT sku, COUNT(*) AS cnt,
           GROUP_CONCAT(cost_price) AS prices,
           GROUP_CONCAT(date_from) AS dates
    FROM product_cost_history
    GROUP BY sku
    HAVING cnt > 1
    LIMIT 15
""").fetchall()
print(f'\nSKU с 2+ записями (топ-15):')
for r in dupes:
    print(f'  sku={r[0]}, cnt={r[1]}, prices={r[2]}, dates={r[3]}')

# ---------- 3. XLSX ----------
print('\n=== 3. XLSX Точки ===')
xl = pd.read_excel(XLSX, dtype=str)
for col in ['id', 'Название', 'Артикул', 'Штрихкод']:
    xl[col] = xl[col].ffill()
xl = xl[xl['Артикул'].notna() & (xl['Артикул'].str.strip() != '')]
xl['Себестоимость'] = pd.to_numeric(
    xl['Себестоимость'].replace('-- не указано --', pd.NA), errors='coerce')
xl = xl.dropna(subset=['Себестоимость'])
print(f'Строк: {len(xl)}')
print(f'Уникальных Артикулов: {xl["Артикул"].nunique()}')
print(f'Дублей: {len(xl) - xl["Артикул"].nunique()}')

diff = xl.groupby('Артикул')['Себестоимость'].nunique()
multi = diff[diff > 1]
print(f'\nАртикулов с РАЗНЫМИ ценами: {len(multi)}')
for offer in list(multi.index)[:15]:
    prices = xl.loc[xl['Артикул']==offer, 'Себестоимость'].tolist()
    print(f'  {offer}: {prices}')

# ---------- 4. Сверка CSV vs XLSX ----------
print('\n=== 4. Сверка CSV ↔ XLSX (последняя цена) ===')
xl_last = xl.groupby('Артикул', as_index=False).last()
xl_map = dict(zip(xl_last['Артикул'].str.strip(), xl_last['Себестоимость']))

csv_map = {}
if 'offer_id' in csv.columns and 'cost_price' in csv.columns:
    for _, r in csv.iterrows():
        csv_map[str(r['offer_id']).strip()] = float(r['cost_price'])

common = set(csv_map) & set(xl_map)
only_csv = set(csv_map) - set(xl_map)
only_xl  = set(xl_map) - set(csv_map)

print(f'Совпадающих offer_id: {len(common)}')
print(f'Только в CSV: {len(only_csv)}')
print(f'Только в XLSX: {len(only_xl)}')

diffs = []
for k in common:
    if abs(csv_map[k] - xl_map[k]) > 0.5:
        diffs.append((k, csv_map[k], xl_map[k]))

print(f'\nРасхождений цены (CSV ≠ XLSX): {len(diffs)}')
for k, c, x in diffs[:30]:
    print(f'  {k}: CSV={c:.0f}, XLSX={x:.0f}, Δ={c-x:+.0f}')

conn.close()