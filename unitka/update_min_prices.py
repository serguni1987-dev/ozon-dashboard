"""unitka/update_min_prices.py — раз в 30 дней ставит минимальную цену и защиту от акций."""
import argparse
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from .ozon_client import OzonClient
from . import unit_core, settings, config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def get_real_prices(client, offer_ids):
    """Получает реальные цены через API v5."""
    real_prices = {}
    for i in range(0, len(offer_ids), 1000):
        chunk = offer_ids[i:i+1000]
        payload = {"filter": {"offer_id": chunk}, "limit": len(chunk), "cursor": ""}
        try:
            data = client._post("/v5/product/info/prices", payload)
            for item in data.get("items", []):
                oid = item.get("offer_id")
                p = float(item.get("price", {}).get("price", 0) or 0)
                real_prices[oid] = p
        except Exception as e:
            logger.error(f"Ошибка запроса цен v5: {e}")
    return real_prices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()

    logger.info("Загружаем настройки и считаем мин. цены...")
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)
    
    tax = {"rate_pct": 5.0, "regime": "income_minus_expense"}
    unit = settings.unit_params(sh)
    
    eco = unit_core.sku_economics(cur, "2026-01-01", "2027-01-01")
    true_floors = unit_core.min_prices(cur, eco, tax, unit)

    cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
    sku_to_offer = {int(r[0]): r[1] for r in cur.fetchall()}
    
    offer_ids = list(sku_to_offer.values())
    client = OzonClient()
    
    logger.info("Получаем реальные цены из Ozon...")
    real_prices = get_real_prices(client, offer_ids)

    tasks = []
    skipped = 0
    
    for sku_int, f_data in true_floors.items():
        offer_id = sku_to_offer.get(sku_int)
        if not offer_id: continue

        min_price = f_data.get("min_direct") or 0
        if min_price == 0: continue

        current_price = real_prices.get(offer_id, 0)
        
        # Если текущая цена ниже нашего «пола», мы не можем поставить защиту. 
        # Пропускаем. auto_repricer поднимет цену.
        if current_price < min_price:
            skipped += 1
            continue
            
        tasks.append({
            "offer_id": offer_id,
            "min_price": round(min_price, 2),
            "current_price": round(current_price, 2)
        })

    logger.info(f"Товаров для установки 'пола': {len(tasks)}")
    logger.info(f"Пропущено (цена уже ниже пола, нужен репрайсер): {skipped}")

    if not tasks:
        return

    if args.dry_run:
        for t in tasks[:10]:
            logger.info(f"  {t['offer_id']}: текущая {t['current_price']:,.0f} ₽, ставим пол {t['min_price']:,.0f} ₽")
        if len(tasks) > 10: logger.info("  ... и другие")
        return

    success = 0
    for t in tasks:
        logger.info(f"Обновляем защиту для {t['offer_id']}: пол {t['min_price']:,.0f} ₽")
        payload = [{
            "offer_id": t["offer_id"],
            "price": str(t["current_price"]), # Передаем текущую цену, чтобы Ozon не ругался
            "min_price": str(t["min_price"]),
            "min_price_for_auto_actions_enabled": True
        }]
        
        try:
            res = client.update_prices(payload)
            result_list = res.get("result", [])
            if result_list and result_list[0].get("updated") is True:
                success += 1
            else:
                errs = result_list[0].get("errors", []) if result_list else "Пустой ответ"
                logger.error(f"  Ошибка Ozon: {errs}")
        except Exception as e:
            logger.error(f"  Ошибка API: {e}")

    logger.info(f"Успешно обновлено: {success} из {len(tasks)}")
    conn.close()

if __name__ == "__main__":
    main()