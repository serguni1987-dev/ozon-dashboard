# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

XLSX = Path(r"C:\Users\sergu\Desktop\проект\analytics_report_daily_2026-10-12_00_28.xlsx")

# 1. Все листы
xl = pd.ExcelFile(XLSX)
print("Листы:", xl.sheet_names)

# 2. Первые 20 строк «как есть» для каждого листа
for sh in xl.sheet_names:
    print("\n" + "=" * 120)
    print(f"ЛИСТ: {sh}")
    print("=" * 120)
    raw = pd.read_excel(XLSX, sheet_name=sh, header=None, nrows=20)
    for i, row in raw.iterrows():
        cells = [("" if pd.isna(v) else str(v))[:28] for v in row.tolist()]
        print(f"{i:>3} | " + " | ".join(cells))

# 3. Колонки «как прочитал бы pandas с header=0..5»
for h in range(0, 6):
    try:
        df = pd.read_excel(XLSX, sheet_name=xl.sheet_names[0], header=h, nrows=0)
        print(f"\nheader={h}: {list(df.columns)}")
    except Exception as e:
        print(f"\nheader={h}: ошибка {e}")