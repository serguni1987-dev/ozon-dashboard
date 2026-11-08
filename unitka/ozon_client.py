import os
import requests
import logging
import time
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", ".env")
load_dotenv(env_path)

logger = logging.getLogger(__name__)

class OzonClient:
    def __init__(self):
        self.client_id = os.getenv("OZON_CLIENT_ID")
        self.api_key = os.getenv("OZON_API_KEY")
        self.base_url = "https://api-seller.ozon.ru"
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def _post(self, path, payload, retries=3):
        url = self.base_url + path
        for attempt in range(retries):
            try:
                # Увеличиваем таймаут до 120 секунд
                r = requests.post(url, headers=self.headers, json=payload, timeout=120)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при запросе к {path} (попытка {attempt+1}/{retries}). Ждем 5 сек...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Ошибка запроса к {path}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Текст ответа: {e.response.text[:500]}")
                return None
        logger.error(f"Не удалось выполнить запрос к {path} после {retries} попыток.")
        return None