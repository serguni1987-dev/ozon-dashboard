import sqlite3
from pathlib import Path
from unitka import config

con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== КТО ЧИТАЕТ ИЗ КАКОЙ ТАБЛИЦЫ? ===")
files = ["calc_funnel.py", "calc_abc_xyz.py", "calc_unit_summary.py",
         "calc_pulse.py", "calc_seasonality.py", "calc_forecast.py",
         "calc_recommendations.py", "_diag/update_data_status.py"]
base = Path(r"C:\Users\sergu\Desktop\проект\unitka")

for f in files:
    path = base / f
    if not path.exists():
        print(f"  {f:30} → НЕ НАЙДЕН")
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    has_manual = "analytics_manual" in text
    has_sales = "sales_daily" in text
    if has_manual and has_sales:
        print(f"  {f:30} → читает ОБЕ")
    elif has_manual:
        print(f"  {f:30} → analytics_manual")
    elif has_sales:
        print(f"  {f:30} → sales_daily")
    else:
        print(f"  {f:30} → не использует эти таблицы")
con.close()