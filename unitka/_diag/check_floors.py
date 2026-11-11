from unitka.db import connect
from unitka import unit_core, settings, config
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)

conn = connect()
cur = conn.cursor()

try:
    unit = settings.unit_params(sh)
    print("Настройки unit_params загружены.")
    
    # Берем настройки налогов как в calc_margin
    # Для простоты ставим те же дефолты
    tax = {"rate_pct": 5.0, "regime": "income_minus_expense"}
    
    eco = unit_core.sku_economics(cur, "2026-01-01", "2027-01-01")
    print(f"Рассчитано экономики для {len(eco)} SKU.")
    
    true_floors = unit_core.min_prices(cur, eco, tax, unit)
    print(f"Рассчитано мин. цен для {len(true_floors)} SKU.")
    
    if len(true_floors) > 0:
        print("\n=== ПРИМЕРЫ КЛЮЧЕЙ И ЗНАЧЕНИЙ В true_floors ===")
        for k, v in list(true_floors.items())[:3]:
            print(f"Ключ: {repr(k)} (тип {type(k)})")
            print(f"Значение: {v}")
            print("-" * 20)
    else:
        print("Словарь true_floors пуст!")
        # Возможно, ошибка в eco?
        if len(eco) > 0:
            print("Пример ключей в eco:")
            for k in list(eco.keys())[:3]:
                print(repr(k))

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    conn.close()