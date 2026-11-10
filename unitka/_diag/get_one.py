from unitka import config
from unitka.ozon_client import OzonClient
import json
config.check_credentials()
c = OzonClient()

for pn in ["50313579-0458-1", "76421118-0054-1", "50438345-0435-1",
           "0115723697-0071-1", "25456394-0146-1"]:
    print(f"\n=== {pn} ===")
    try:
        r = c._post("/v3/posting/fbs/get", {"posting_number": pn, "with": {"analytics_data": True, "financial_data": True}})
        res = r.get("result") or {}
        if not res:
            print("  ПУСТО:", r)
            continue
        print(f"  status: {res.get('status')}")
        print(f"  in_process_at: {res.get('in_process_at')}")
        print(f"  shipment_date: {res.get('shipment_date')}")
        print(f"  delivering_date: {res.get('delivering_date')}")
        print(f"  cancellation: {json.dumps(res.get('cancellation'), ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  ОШИБКА: {e}")