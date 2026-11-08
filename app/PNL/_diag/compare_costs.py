import os, sqlite3
import pandas as pd

XLSX = r'C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx'
CSV  = r'C:\Users\sergu\Desktop\проект\costs_all.csv'
DB   = r'C:\Users\sergu\Desktop\проект\app\ozon.db'

print('XLSX exists:', os.path.exists(XLSX))
if not os.path.exists(XLSX):
    print('!!! Положи XLSX в C:\\Users\\sergu\\Desktop\\проект\\')
    raise SystemExit

# --- XLSX: последняя цена по Артикулу ---
xl = pd.read_excel(XLSX, dtype=str)
for col in ['id', 'Название', 'Артикул', 'Штрихкод']:
    xl[col] = xl[col].ffill()
xl = xl[xl['Артикул'].notna() & (xl['Артикул'].str.strip() != '')].copy()
xl['Себестоимость'] = pd.to_numeric(
    xl['Себестоимость'].replace('-- не указано --', pd.NA), errors='coerce')
xl = xl.dropna(subset=['Себестоимость'])
xl_last = xl.groupby('Артикул', as_index=False).last()
xl_map = dict(zip(xl_last['Артикул'].str.strip(), xl_last['Себестоимость']))

# --- CSV ---
csv = pd.read_csv(CSV, sep=';', dtype=str)
csv['cost_price'] = pd.to_numeric(csv['cost_price'], errors='coerce')
csv_map = dict(zip(csv['offer_id'].astype(str).str.strip(), csv['cost_price']))

# --- БД: смотрим SKU, которые продавались в янв-фев ---
conn = sqlite3.connect(DB)
jan_feb_sku = set()
for sku, in conn.execute("""
    SELECT DISTINCT sku FROM monthly_realization_rows
    WHERE month IN ('2026-01','2026-02') AND is_return = 0
"""):
    jan_feb_sku.add(sku)

# маппинг sku → offer_id
sku_offer = {}
for sku, offer in conn.execute("""
    SELECT DISTINCT sku, offer_id FROM monthly_realization_rows
    WHERE month IN ('2026-01','2026-02') AND offer_id IS NOT NULL
"""):
    sku_offer[sku] = offer

# цена из БД (то, что видит P&L)
db_cost = {}
for sku, in ((s,) for s in jan_feb_sku):
    r = conn.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from<'2026-03-01'
        ORDER BY date_from DESC, id DESC LIMIT 1
    """, (sku,)).fetchone()
    db_cost[sku] = r[0] if r and r[0] else 0

conn.close()

# --- Сверка ---
print(f'\nSKU продавалось в янв-фев: {len(jan_feb_sku)}')
print(f'{"sku":>12} {"offer_id":>22} {"наша БД":>9} {"CSV":>9} {"XLSX":>9} {"Δ(БД−XLSX)":>12}')

diffs = 0
for sku in sorted(jan_feb_sku):
    offer = sku_offer.get(sku, '?')
    db_c = db_cost.get(sku, 0)
    csv_c = csv_map.get(str(offer), None)
    xl_c = xl_map.get(str(offer), None)

    flag = ''
    delta = ''
    if xl_c is not None and db_c:
        d = db_c - xl_c
        if abs(d) > 0.5:
            diffs += 1
            flag = '  ← РАСХОЖДЕНИЕ'
            delta = f'{d:+.0f}'

    print(f'{sku:>12} {str(offer):>22} {db_c:>9.0f} '
          f'{csv_c if csv_c is not None else "—":>9} '
          f'{xl_c if xl_c is not None else "—":>9} '
          f'{delta:>12}{flag}')

print(f'\nSKU с расхождением БД vs XLSX: {diffs}')