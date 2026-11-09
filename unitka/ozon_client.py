import json
import time
import urllib.request
import urllib.error
from . import config

OZON_BASE = "https://api-seller.ozon.ru"

class OzonError(Exception):
    pass

class OzonClient:
    def __init__(self):
        self.client_id = config.OZON_CLIENT_ID
        self.api_key = config.OZON_API_KEY
        self.base = config.OZON_BASE_URL
        if not self.client_id or not self.api_key:
            raise ValueError("Нет ключей Ozon (проверьте app\\.env)")

    def _post(self, path: str, payload: dict) -> dict:
        url = self.base + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }
        delay, last_err = 1.0, None
        for attempt in range(1, 4):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", errors="replace")
                if e.code != 429 and 400 <= e.code < 500:
                    raise OzonError(f"HTTP {e.code} {path}: {text}") from e
                last_err = OzonError(f"HTTP {e.code} {path}: {text}")
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = OzonError(f"Network {path}: {e}")
            if attempt < 3:
                time.sleep(delay)
                delay *= 2
        raise last_err or OzonError(f"Failed: {path}")

    def accrual_by_day(self, date: str, last_id: str = "") -> dict:
        return self._post("/v1/finance/accrual/by-day", {"date": date, "last_id": last_id})

    def accrual_by_day_all(self, date: str) -> list:
        out, last_id = [], ""
        while True:
            data = self.accrual_by_day(date, last_id)
            out.extend(data.get("accruals") or [])
            last_id = data.get("last_id") or ""
            if not last_id:
                break
        return out