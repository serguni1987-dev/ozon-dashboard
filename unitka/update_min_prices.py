"""unitka/update_min_prices.py — раз в 30 дней ставит минимальную цену и защиту от акций.
Запуск: py -m unitka.update_min_prices [--dry-run]
"""
import argparse
import logging
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from .ozon_client import OzonClient
from . import unit_core, settings, config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

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
    
    # Берем ставку налога из настроек (как в calc_margin)
    tax = {"rate_pct": 5.0, "regime": "income_minus_expense"} 
    unit = settings.unit_params(sh)
    
    eco = unit_core.sku_economics(cur, "2026-01-01", "2027-01-01")
    true_floors = unit_core.min_prices(cur, eco, tax, unit)

    cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
    sku_to_offer = {int(r[0]): r[1] for r in cur.fetchall()}

    tasks = []
    for sku_int, f_data in true_floors.items():
        offer_id = sku_to_offer.get(sku_int)
        if not offer_id: continue

        min_price = f_data.get("min_direct") or 0
        if min_price > 0:
            tasks.append({
                "offer_id": offer_id,
                "min_price": round(min_price, 2)
            })

    logger.info(f"Найдено товаров для установки 'пола': {len(tasks)}")

    if not tasks:
        return

    if args.dry_run:
        for t in tasks[:10]:
            logger.info(f"  {t['offer_id']}: min_price = {t['min_price']:,.0f} ₽")
        if len(tasks) > 10: logger.info("  ... и другие")
        return

    client = OzonClient()
    success = 0
    
    for t in tasks:
        logger.info(f"Обновляем защиту для {t['offer_id']}: мин. цена {t['min_price']:,.0f} ₽")
        payload = [{
            "offer_id": t["offer_id"],
            "min_price": str(t["min_price"]),
            "min_price_for_auto_actions_enabled": True # Включаем защиту!
        }]
        
        try:
            res = client.update_prices(payload)
            # Проверяем ответ Ozon (защита от "тихого" отказа)
            result_list = res.get("result", [])
            if result_list and result_list[0].get("updated") is True:
                success += 1
            else:
                errs = result_list[0].get("errors", []) if result_list else "Пустой ответ"
                if "action_price_enabled_min_price_missing" in str(errs):
                    logger.warning(f"  [{t['offer_id']}] Ozon требует выключить автодействия. Пробуем False...")
                    payload[0]["min_price_for_auto_actions_enabled"] = False
                    res2 = client.update_prices(payload)
                    if res2.get("result", [{}])[0].get("updated"):
                        success += 1
                    else:
                        logger.error(f"  Ошибка при повторе: {res2}")
                else:
                    logger.error(f"  Ошибка Ozon: {errs}")
        except Exception as e:
            logger.error(f"  Ошибка API: {e}")

    logger.info(f"Успешно обновлено: {success} из {len(tasks)}")
    conn.close()

if __name__ == "__main__":
    main()