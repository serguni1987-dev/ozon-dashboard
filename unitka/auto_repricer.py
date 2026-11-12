"""unitka/auto_repricer.py — динамическое изменение цены по индексу и конкурентам."""
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


def can_update(conn, offer_id):
    one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("SELECT COUNT(*) FROM price_update_log WHERE offer_id = ? AND updated_at > ?", (offer_id, one_hour_ago))
    return cur.fetchone()[0] < 10


def get_real_prices(client, offer_ids):
    """Получает реальные цены через API v5 (постранично)."""
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
    parser.add_argument("--dry-run", action="store_true", help="Только показать план")
    parser.add_argument("--limit", type=int, default=0, help="Сколько товаров обновить (0 = все)")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    conn.execute("CREATE TABLE IF NOT EXISTS price_update_log (offer_id TEXT, updated_at TEXT, old_price REAL, new_price REAL)")
    conn.commit()

    logger.info("Считаем минимальные цены (пол)...")
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
    for sku_int, f_data in true_floors.items():
        offer_id = sku_to_offer.get(sku_int)
        if not offer_id: continue
        
        current_price = real_prices.get(offer_id, 0)
        if current_price == 0: continue
        
        min_price = f_data.get("min_direct") or 0
        if min_price == 0: continue

        # ЛОГИКА ЦЕНООБРАЗОВАНИЯ:
        # Если мы продаем в убыток (ниже пола) -> поднимаем, но не более чем на 15% за раз
        if current_price < min_price:
            target_price = round(min_price * 1.02, 2)       # Идеальная цена (пол + 2%)
            max_step_price = round(current_price * 1.15, 2) # Максимум +15% за раз
            
            if target_price > max_step_price:
                new_price = max_step_price
                reason = "Выход из убытка (плавный шаг +15%)"
            else:
                new_price = target_price
                reason = "Выход из убытка"
                
            tasks.append({"offer_id": offer_id, "old": current_price, "new": new_price, "reason": reason})

    logger.info(f"Найдено задач: {len(tasks)}")
    if not tasks: 
        conn.close()
        return

    # Сортируем по размеру убытка (сначала самые дешевые/убыточные)
    tasks.sort(key=lambda x: x["old"], reverse=False) 
    if args.limit > 0: 
        tasks = tasks[:args.limit]

    if args.dry_run:
        for t in tasks:
            logger.info(f"  {t['offer_id']}: {t['old']:,.0f} -> {t['new']:,.0f} ({t['reason']})")
        conn.close()
        return

    # Отправка в API
    success = 0
    for t in tasks:
        if not can_update(conn, t["offer_id"]):
            logger.warning(f"  [{t['offer_id']}] Лимит 10 раз в час. Пропускаем.")
            continue

        logger.info(f"  Меняем {t['offer_id']}: {t['old']:,.0f} -> {t['new']:,.0f}")
        payload = [{"offer_id": t["offer_id"], "price": str(t["new"])}]
        
        try:
            res = client.update_prices(payload)
            result_list = res.get("result", [])
            # Проверяем ответ Ozon!
            if result_list and result_list[0].get("updated") is True:
                conn.execute("INSERT INTO price_update_log VALUES (?, ?, ?, ?)", 
                             (t["offer_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t["old"], t["new"]))
                conn.commit()
                success += 1
            else:
                logger.error(f"  Отклонено Ozon: {result_list[0].get('errors') if result_list else 'Пустой ответ'}")
        except Exception as e:
            logger.error(f"  Ошибка API: {e}")

    logger.info(f"Успешно обновлено: {success} из {len(tasks)}")
    conn.close()

if __name__ == "__main__":
    main()