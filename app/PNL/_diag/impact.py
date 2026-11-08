import sqlite3
import pandas as pd

XLSX = r'C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx'
CSV  = r'C:\Users\sergu\Desktop\проект\costs_all.csv'
DB   = r'C:\Users\sergu\Desktop\проект\app\ozon.db'

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

# --- CSV: текущая цена ---
csv = pd.read_csv(CSV, sep=';', dtype=str)
csv['cost_price'] = pd.to_numeric(csv['cost_price'], errors='coerce')
csv_map = dict(zip(csv['offer_id'].astype(str).str.strip(), csv['cost_price']))

# --- Кол-во за янв и фев по offer_id ---
conn = sqlite3.connect(DB)
qty_by_offer = {}
for offer, qty in conn.execute("""
    SELECT offer_id, SUM(quantity) FROM monthly_realization_rows
    WHERE month IN ('2026-01','2026-02') AND is_return=0 AND offer_id IS NOT NULL
    GROUP BY offer_id
"""):
    qty_by_offer[offer] = qty
conn.close()

# --- 9 SKU с расхождением ---
offers = ['CH036177','CH027E4','CH029E4','OCPR013E416030','SM001150210',
          'SM002180215','OCER017E416030','LVR007E416030','MSR016D414030']

print(f'{"offer":>22} {"CSV":>8} {"XLSX":>8} {"qty J+F":>9} {"Δ/шт":>8} {"Δ итог":>10}')
total_delta = 0
for o in offers:
    c = csv_map.get(o, 0)
    x = xl_map.get(o, 0)
    q = qty_by_offer.get(o, 0)
    d = (c - x) * q
    total_delta += d
    print(f'{o:>22} {c:>8.0f} {x:>8.0f} {q:>9.0f} {c-x:>+8.0f} {d:>+10.0f}')
print(f'{"ИТОГО":>22} {"":>8} {"":>8} {"":>9} {"":>8} {total_delta:>+10.0f}')

print(f'\nТекущее расхождение P&L:')
print(f'  январь: +3 271 ₽ (наш 151 237 vs Точка 147 966)')
print(f'  февраль: +6 659 ₽ (наш 111 458 vs Точка 104 799)')
print(f'  сумма:  +9 930 ₽')
print(f'\nЕсли переключить CSV → XLSX, COGS изменится на {total_delta:+.0f} ₽')