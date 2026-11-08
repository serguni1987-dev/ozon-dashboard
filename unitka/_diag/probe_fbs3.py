"""FBS с миллисекундами."""
import json
import sys
from .. import config
from ..ozon_client import OzonClient


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-09-15"
    config.check_credentials()
    client = OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY,
                        base=config.OZON_BASE_URL)

    resp = client._post("/v3/posting/fbs/list", {
        "dir": "ASC",
        "filter": {
            "processed_at_from": day + "T00:00:00.000Z",
            "processed_at_to":   day + "T23:59:59.999Z",
        },
        "limit": 100,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    })
    result = resp.get("result") or resp
    postings = result.get("postings") or []
    print(f"FBS за {day}: {len(postings)} отправлений")
    if postings:
        print("--- первое ---")
        print(json.dumps(postings[0], ensure_ascii=False, indent=2)[:2500])
        statuses = {}
        for p in postings:
            statuses[p.get("status")] = statuses.get(p.get("status"), 0) + 1
        print("--- статусы ---", statuses)


if __name__ == "__main__":
    main()
