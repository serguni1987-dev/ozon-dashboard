from unitka.auto_repricer import get_sku_data, get_real_prices
from unitka.ozon_client import OzonClient
from unitka.db import connect
from unitka import unit_core, settings
import gspread
from google.oauth2.service_account import Credentials
from unitka import config

# Получаем доступ к таблице (чтобы взять настройки)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)

conn = connect()
cur = conn.cursor()
skus = get_sku_data(cur)

# Считаем правильные мин. цены (как в calc_margin)
tax = {"rate_pct": 5.0, "regime": "income_minus_expense"} # Упрощенно
unit = settings.unit_params(sh)
eco = unit_core.sku_economics(cur, "2026-01-01", "2027-01-01")
true_floors = unit_core.min_prices(cur, eco, tax, unit)

client = OzonClient()
offer_ids = [s["offer_id"] for s in skus]
real_prices = get_real_prices(client, offer_ids)

print(f"{'Артикул':<15} | {'Реальная цена':>12} | {'Мин. цена (в ноль)':>18} | {'Статус':>10}")
print("-" * 65)
for s in skus:
    offer = s["offer_id"]
    real = real_prices.get(offer, 0)
    
    # Ищем правильную мин цену
    f_data = true_floors.get(s["sku"]) or true_floors.get(str(s["sku"])) or true_floors.get(offer) or {}
    min_price_real = f_data.get("min_price_zero", f_data.get("min_price", 0.0))
    
    status = "🔴 УБЫТОК" if real < min_price_real else "🟢 ОК"
    if real == 0: status = "❓ НЕТ ЦЕНЫ"
    
    print(f"{offer:<15} | {real:>12,.0f} | {min_price_real:>18,.0f} | {status:>10}")
    
conn.close()