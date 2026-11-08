import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from .ozon_performance_client import OzonPerformanceClient
from .db import connect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

def _f(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    return float(str(v).replace(",", ".").replace(" ", ""))

def init_db():
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ad_campaigns_daily (
            date TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            campaign_name TEXT,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            expense REAL DEFAULT 0,
            orders INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id)
        )
    """)
    conn.commit()
    conn.close()

def main(days_back=30):
    logger.info("Загрузка статистики рекламы (Performance API)...")
    init_db()
    client = OzonPerformanceClient()
    conn = connect()
    cur = conn.cursor()

    # 1. Список кампаний
    campaign_names = {}
    active_campaigns = []
    
    try:
        resp = client.get("/api/client/campaign")
        campaigns = resp.get("list", []) if isinstance(resp, dict) else resp
        logger.info(f"Всего кампаний в аккаунте: {len(campaigns)}")
        
        for c in campaigns:
            camp_id = str(c.get("id", ""))
            name = c.get("title", "")
            state = c.get("state", "")
            if camp_id:
                campaign_names[camp_id] = name
                if state == "CAMPAIGN_STATE_RUNNING":
                    active_campaigns.append(camp_id)
                    
        logger.info(f"Активных кампаний: {len(active_campaigns)}")
        if not active_campaigns:
            logger.warning("Нет активных кампаний. Загрузка статистики невозможна.")
            conn.close()
            return
        logger.info(f"ID активных кампаний: {active_campaigns}")
    except Exception as e:
        logger.error(f"Ошибка списка кампаний: {e}")
        conn.close()
        return

    # 2. Дневная статистика (GET)
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=days_back)
    
    params = {
        "campaignIds": ",".join(active_campaigns),
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
    }
    
    try:
        logger.info(f"Запрос статистики (GET) с {date_from} по {date_to}")
        stats = client.get("/api/client/statistics/daily/json", params=params)
        
        # Сохраняем сырой ответ для отладки
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        sample_path = OUT_DIR / "ads_sample.json"
        with sample_path.open("w", encoding="utf-8") as fh:
            json.dump(stats, fh, ensure_ascii=False, indent=2)
        logger.info(f"Сырой ответ сохранен: {sample_path}")
        
        rows = []
        if isinstance(stats, dict):
            if "rows" in stats:
                rows = stats["rows"]
                logger.info(f"Найдено строк в 'rows': {len(rows)}")
                if rows:
                    logger.info(f"Пример строки: {rows[0]}")
            elif "campaigns" in stats:
                # На случай старой структуры: разворачиваем dailyStatistics
                for c in stats["campaigns"]:
                    camp_id = str(c.get("id", ""))
                    for d in c.get("dailyStatistics", []):
                        d["campaignId"] = camp_id
                        rows.append(d)
                logger.info(f"Развернуто из 'campaigns': {len(rows)}")
            else:
                logger.warning(f"Неизвестные ключи: {list(stats.keys())}")
        elif isinstance(stats, list):
            rows = stats
            logger.info(f"Получен список строк: {len(rows)}")
        
        total_saved = 0
        for item in rows:
            camp_id = str(item.get("campaignId") or item.get("campaign_id") or "")
            if not camp_id:
                continue
            date_str = item.get("date") or item.get("day")
            if not date_str:
                continue
            
            cur.execute("""
                INSERT OR REPLACE INTO ad_campaigns_daily
                (date, campaign_id, campaign_name, impressions, clicks, expense, orders, revenue)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                camp_id,
                campaign_names.get(camp_id, ""),
                int(_f(item.get("impressions"))),
                int(_f(item.get("clicks"))),
                _f(item.get("expense") or item.get("moneySpent")),
                int(_f(item.get("orders") or item.get("orderedUnits"))),
                _f(item.get("revenue") or item.get("orderedRevenue")),
            ))
            total_saved += 1
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Текст ответа Ozon: {e.response.text}")
        conn.close()
        return

    conn.commit()
    conn.close()
    logger.info(f"Сохранено строк статистики: {total_saved}")

if __name__ == '__main__':
    main()