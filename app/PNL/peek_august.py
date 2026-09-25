"""peek_august.py — читает отчёт о реализации за август 2026 через Ozon API.
НИЧЕГО НЕ ПИШЕТ в БД. Только печатает агрегированные суммы."""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

CLIENT_ID = os.getenv("OZON_CLIENT_ID")
API_KEY   = os.getenv("OZON_API_KEY")

if not CLIENT_ID or not API_KEY:
    raise SystemExit("Не нашёл OZON_CLIENT_ID / OZON_API_KEY в .env")

H = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}
URL = "https://api-seller.ozon.ru/v2/finance/realization"

MONTH, YEAR = 8, 2026

print(f"═══ Отчёт о реализации за {YEAR}-{MONTH:02d} ═══════════════")
r = requests.post(URL, headers=H, json={"month": MONTH, "year": YEAR}, timeout=120)
print(f"HTTP: {r.status_code}")
if r.status_code != 200:
    print(f"Ошибка: {r.text[:500]}")
    raise SystemExit(1)

data = r.json()
header = data.get("result", {}).get("header", {})
rows = data.get("result", {}).get("rows", [])

print(f"\n── Титульный лист ────────────────────────")
print(f"  Номер отчёта:   {header.get('number')}")
print(f"  Дата документа: {header.get('doc_date')}")
print(f"  Период:         {header.get('start_date')} — {header.get('stop_date')}")
print(f"  Плательщик:     {header.get('payer_name')}")

print(f"\n── Строк в отчёте: {len(rows)} ─────────────────")

# Суммы
sum_seller_price = 0.0   # ваша цена * кол-во
sum_sale_price   = 0.0   # цена покупателя
sum_commission   = 0.0   # комиссия Ozon
sum_bonus        = 0.0   # баллы за скидки
sum_coinvest     = 0.0   # соинвестирование
sum_logistics    = 0.0   # логистика
sum_stars        = 0.0   # звёзды
sum_return_comm  = 0.0   # комиссия по возвратам
sum_return_log   = 0.0   # логистика возвратов

for row in rows:
    dc = row.get("delivery_commission", {}) or {}
    rc = row.get("return_commission", {}) or {}
    qty = dc.get("quantity", 0) or 0
    seller_price = row.get("seller_price_per_instance", 0) or 0

    sum_seller_price += seller_price * qty
    sum_sale_price   += dc.get("amount", 0) or 0
    sum_commission   += dc.get("commission", 0) or 0
    sum_bonus        += dc.get("bonus", 0) or 0
    sum_coinvest     += dc.get("bank_coinvestment", 0) or 0
    sum_logistics    += dc.get("standard_fee", 0) or 0
    sum_stars        += dc.get("stars", 0) or 0

    sum_return_comm  += rc.get("commission", 0) or 0
    sum_return_log   += rc.get("standard_fee", 0) or 0

print(f"\n── Агрегаты по строкам (сырые из API) ────")
print(f"  seller_price_per_instance * qty: {sum_seller_price:>16,.2f}")
print(f"  amount (sale_price):              {sum_sale_price:>16,.2f}")
print(f"  commission:                       {sum_commission:>16,.2f}")
print(f"  bonus:                            {sum_bonus:>16,.2f}")
print(f"  bank_coinvestment:                {sum_coinvest:>16,.2f}")
print(f"  standard_fee (логистика):         {sum_logistics:>16,.2f}")
print(f"  stars:                            {sum_stars:>16,.2f}")
print(f"  return.commission:                {sum_return_comm:>16,.2f}")
print(f"  return.standard_fee:              {sum_return_log:>16,.2f}")

print(f"\n── Итог (как в личном кабинете) ──────────")
gross_comm = sum_commission + sum_return_comm
sale_less_returns = sum_sale_price - sum_return_comm
total_to_charge = sale_less_returns + sum_bonus + sum_coinvest

print(f"  Сумма отчёта (sale_price):        {sum_sale_price:>16,.2f}")
print(f"  Гросс-комиссия Ozon:              {gross_comm:>16,.2f}")
print(f"  Баллы за скидки:                  {sum_bonus:>16,.2f}")
print(f"  Соинвестирование:                 {sum_coinvest:>16,.2f}")
print(f"  Логистика (standard_fee):         {sum_logistics:>16,.2f}")
print(f"  Звёзды:                           {sum_stars:>16,.2f}")
print(f"\n  Всего к начислению:               {total_to_charge:>16,.2f}")

# Сохраняем сырой ответ для дальнейшего разбора
with open("peek_august_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"\n[OK] Сырой ответ сохранён: peek_august_raw.json")