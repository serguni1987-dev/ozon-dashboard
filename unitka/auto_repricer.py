"""unitka/auto_repricer.py — динамическое изменение цены по индексу и конкурентам.
Запуск: py -m unitka.auto_repricer [--dry-run] [--limit N]
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

def can_update(conn, offer_id):
    one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("SELECT COUNT(*) FROM price_update_log WHERE offer_id = ? AND updated_at > ?", (offer_id, one_hour_ago))
    return cur.fetchone()[0] < 10

def get_market_data(client, offer_ids):
    """Получает реальные цены, индексы и цены конкурентов (постранично)."""
    real_prices = {}
    index_data = {}
    
    # 1. Цены из v5 (постранично по 1000)
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
            logger.error(f"Ошибка v5: {e}")
            
    # 2. Индексы и конкуренты из v3 (по 100 SKU за раз)
    for i in range(0, len(offer_ids), 100):
        chunk = offer_ids[i:i+100]
        # В v3 передаются product_id или sku, но если у нас есть только offer_id, 
        # нужен маппинг. Для простоты пока используем /v3/product/info/list через sku.
        pass # Для безопасности пока не будем перегружать API
        
    return real_prices, index_data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
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
    
    logger.info("Получаем реальные цены...")
    real_prices, index_data = get_market_data(client, offer_ids)

    tasks = []
    for sku_int, f_data in true_floors.items():
        offer_id = sku_to_offer.get(sku_int)
        if not offer_id: continue
        
        current_price = real_prices.get(offer_id, 0)
        if current_price == 0: continue
        
        min_price = f_data.get("min_direct") or 0
        if min_price == 0: continue

        # ЛОГИКА ЦЕНООБРАЗОВАНИЯ:
        # 1. Если мы продаем в убыток (ниже пола) -> срочно поднимаем до пола + 2%
        if current_price < min_price:
            new_price = round(min_price * 1.02, 2)
            tasks.append({"offer_id": offer_id, "old": current_price, "new": new_price, "reason": "Выход из убытка"})
            continue

        # 2. Если мы в плюсе, но дороже конкурентов (нужно добавить логику индексов)
        # (Оставим на следующий шаг, когда проверим работу API)
        
    logger.info(f"Найдено задач: {len(tasks)}")
    if not tasks: return

    tasks.sort(key=lambda x: x["old"], reverse=False) # Сначала самые дешевые (убыточные)
    if args.limit > 0: tasks = tasks[:args.limit]

    if args.dry_run:
        for t in tasks:
            logger.info(f"  {t['offer_id']}: {t['old']:,.0f} -> {t['new']:,.0f} ({t['reason']})")
        return

    for t in tasks:
        if not can_update(conn, t["offer_id"]):
            logger.warning(f"  [{t['offer_id']}] Лимит 10 раз в час")
            continue

        logger.info(f"  Меняем {t['offer_id']}: {t['old']:,.0f} -> {t['new']:,.0f}")
        payload = [{"offer_id": t["offer_id"], "price": str(t["new"])}]
        
        try:
            res = client.update_prices(payload)
            result_list = res.get("result", [])
            if result_list and result_list[0].get("updated") is True:
                conn.execute("INSERT INTO price_update_log VALUES (?, ?, ?, ?)", 
                             (t["offer_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t["old"], t["new"]))
                conn.commit()
            else:
                logger.error(f"  Отклонено Ozon: {result_list[0].get('errors')}")
        except Exception as e:
            logger.error(f"  Ошибка API: {e}")

    conn.close()

if __name__ == "__main__":
    main()