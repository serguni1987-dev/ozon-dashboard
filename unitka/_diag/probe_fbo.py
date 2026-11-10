from unitka import config
from unitka.ozon_client import OzonClient
import json
config.check_credentials()
c = OzonClient()

payload = {
    "dir": "ASC",
    "filter": {"since": "2026-09-01T00:00:00.000Z",
               "to":   "2026-09-30T23:59:59.999Z"},
    "limit": 3,
    "offset": 0,
    "with": {"analytics_data": True, "financial_data": True},
}
try:
    r = c._post("/v2/posting/fbo/list", payload)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str)[:3000])
except Exception as e:
    print(f"ОШИБКА: {e}")