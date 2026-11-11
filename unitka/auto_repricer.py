"""unitka/auto_repricer.py — безопасное повышение цен до минимального уровня."""
import argparse
import logging
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from .ozon_client import OzonClient
from . import unit_core, settings, config
from .finance_core import tax_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_update_log (
            offer_id TEXT, updated_at TEXT, old_price REAL, new_price REAL
        )
    """)
    conn.commit()


def can_update(conn, offer_id):
    one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("SELECT COUNT(*) FROM price_update_log WHERE offer_id = ? AND updated_at > ?", (offer_id, one_hour_ago))
    return cur.fetchone()[0] < 10


def get_real_prices(client, offer_ids):
    payload = {"filter": {"offer_id": offer_ids}, "limit": len(offer_ids), "cursor": ""}
    try:
        data = client._post("/v5/product/info/prices", payload)
        items = data.get("items", [])
        result = {}
        for item in items:
            offer_id = item.get("offer_id")
            price_data = item.get("price", {})
            real_price = float(price_data.get("price", 0) or 0)
            if real_price == 0:
                real_price = float(price_data.get("marketing_seller_price", 0) or 0)
            result[offer_id] = real_price
        return result
    except Exception as e:
        logger.error(f"Ошибка запроса цен из Ozon: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Только показать план")
    parser.add_argument("--limit", type=int, default=0, help="Сколько товаров обновить (0 = все)")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    init_db(conn)

    # 1. Загружаем настройки и считаем мин. цены через unit_core
    logger.info("Загружаем настройки и считаем мин. цены...")
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)
    
    # Налог — из листа «НАСТРОЙКИ», как в «Юнит-сводке». Раньше здесь стоял режим
    # "income_minus_expense": unit_core его не узнавал и вместо минимального налога 1 %
    # закладывал все 5 % — мин. цена получалась на 7–10 % выше, чем в «Юнит-сводке».
    tax = tax_settings(sh)
    unit = settings.unit_params(sh)

    year = datetime.now().year
    eco = unit_core.sku_economics(cur, f"{year}-01-01", f"{year + 1}-01-01")
    true_floors = unit_core.min_prices(cur, eco, tax, unit)

    # 2. Получаем offer_id для всех SKU из sku_map
    cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
    sku_to_offer = {int(r[0]): r[1] for r in cur.fetchall()}

    # 3. Запрашиваем реальные цены
    offer_ids = list(sku_to_offer.values())
    if not offer_ids:
        logger.warning("Нет offer_id в базе.")
        return

    logger.info(f"Запрашиваем реальные цены для {len(offer_ids)} offer_id...")
    client = OzonClient()
    real_prices = get_real_prices(client, offer_ids)

    # 4. Формируем задачи
    tasks = []
    for sku_int, f_data in true_floors.items():
        offer_id = sku_to_offer.get(sku_int)
        if not offer_id:
            continue

        real_price = real_prices.get(offer_id, 0)
        if real_price == 0:
            continue  # Товара нет в наличии или скрыт

        # Берем min_direct (цена в ноль). Можно взять min_full, чтобы покрывать рекламу.
        min_price = f_data.get("min_direct") or 0

        if min_price > 0 and real_price < min_price:
            new_price = round(min_price * 1.02, 2)  # +2% запас
            tasks.append({
                "offer_id": offer_id,
                "sku": sku_int,
                "old_price": real_price,
                "new_price": new_price,
                "min_price": min_price
            })

    logger.info(f"Найдено товаров для репрайсинга: {len(tasks)}")
    
    # Сортируем по размеру убытка (сначала самые убыточные)
    tasks.sort(key=lambda t: (t["min_price"] - t["old_price"]), reverse=True)
    
    if args.limit > 0 and len(tasks) > args.limit:
        logger.info(f"Ограничиваем до {args.limit} самых убыточных товаров.")
        tasks = tasks[:args.limit]

    if not tasks:
        logger.info("Все цены в порядке!")
        return

    if args.dry_run:
        logger.info("=== РЕЖИМ DRY-RUN (без отправки в API) ===")
        for t in tasks:
            logger.info(f"  {t['offer_id']} (SKU {t['sku']}): {t['old_price']:,.0f} ₽ -> {t['new_price']:,.0f} ₽ (мин. {t['min_price']:,.0f} ₽)")
        conn.close()
        return

    # 5. Отправка в API
    try:
        for t in tasks:
            if not can_update(conn, t["offer_id"]):
                logger.warning(f"  [{t['offer_id']}] Лимит 10 раз в час. Пропускаем.")
                continue

            logger.info(f"  Обновляем {t['offer_id']}: {t['old_price']:,.0f} ₽ -> {t['new_price']:,.0f} ₽")
            payload = [{
                "offer_id": t["offer_id"],
                "price": str(t["new_price"]),
                "min_price_for_auto_actions_enabled": False
            }]
            client.update_prices(payload)

            conn.execute(
                "INSERT INTO price_update_log (offer_id, updated_at, old_price, new_price) VALUES (?, ?, ?, ?)",
                (t["offer_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), t["old_price"], t["new_price"])
            )
            conn.commit()
        logger.info("Репрайсинг завершен.")
    except Exception as e:
        logger.error(f"Ошибка API: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()