import os
import time
import logging
import requests
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(APP_DIR, "app", ".env")
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

class OzonPerformanceClient:
    BASE = "https://api-performance.ozon.ru"

    def __init__(self):
        self.client_id = os.getenv("OZON_PERF_CLIENT_ID")
        self.client_secret = os.getenv("OZON_PERF_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(f"Не найдены OZON_PERF_CLIENT_ID / OZON_PERF_CLIENT_SECRET в {ENV_PATH}")
        self._token = None
        self._expires_at = 0

    def _get_token(self):
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        r = requests.post(f"{self.BASE}/api/client/token", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 1800)
        return self._token

    def _request(self, method, path, **kwargs):
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }
        
        r = requests.request(method, self.BASE + path, headers=headers, timeout=60, **kwargs)
        
        if r.status_code == 401:
            self._token = None
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            r = requests.request(method, self.BASE + path, headers=headers, timeout=60, **kwargs)
        
        r.raise_for_status()
        return r.json()

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, json=None):
        return self._request("POST", path, json=json)