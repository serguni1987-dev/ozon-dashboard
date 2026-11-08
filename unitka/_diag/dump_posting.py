from unitka import config
from unitka.ozon_client import OzonClient

config.check_credentials()
c = OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY, base=config.OZON_BASE_URL)

payload = {
    "dir": "ASC",
    "filter": {"since": "2026-09-01T00:00:00.000Z",
               "to":   "2026-10-04T23:59:59.999Z"},
    "limit": 1,
    "offset": 0,
    "with": {"analytics_data": True, "financial_data": True},
}
r = c._post("/v3/posting/fbs/list", payload)
import json
print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])