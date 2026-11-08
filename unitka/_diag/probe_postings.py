"""Пробуем разные методы и разные фильтры, чтобы найти наши отправления."""
import json
import sys
from .. import config
from ..ozon_client import OzonClient


def try_method(client, path, payload):
    print(f"\n=== {path} ===")
    try:
        resp = client._post(path, payload)
    except Exception as e:
        print(f"  ОШИБКА: {e}")
        return
    # Печатаем только верхний уровень (без значений)
    print(f"  ключи ответа: {list(resp.keys())}")
    # Проверяем и result.postings, и postings
    postings = (resp.get("result") or {}).get("postings") or resp.get("postings") or []
    print(f"  найдено отправлений: {len(postings)}")
    if postings:
        print("  --- первое отправление ---")
        print(json.dumps(postings[0], ensure_ascii=False, indent=2)[:2500])
        return postings
    return None


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-09-15"
    config.check_credentials()
    client = OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY,
                        base=config.OZON_BASE_URL)

    since = day + "T00:00:00Z"
    to    = day + "T23:59:59Z"

    # 1) FBS с фильтром по дате
    try_method(client, "/v3/posting/fbs/list", {
        "dir": "ASC",
        "filter": {"since": since, "to": to},
        "limit": 100,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    })

    # 2) FBO с фильтром по дате
    try_method(client, "/v3/posting/fbo/list", {
        "dir": "ASC",
        "filter": {"since": since, "to": to},
        "limit": 100,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    })

    # 3) FBS с фильтром по статусу awaiting_deliver и без дат
    try_method(client, "/v3/posting/fbs/list", {
        "dir": "DESC",
        "filter": {"status": "delivered"},
        "limit": 20,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    })

    # 4) FBS только по posting_numbers (если знаем какой-то из дампа)
    try_method(client, "/v3/posting/fbs/list", {
        "dir": "ASC",
        "filter": {"posting_numbers": ["32445444-0228-1"]},
        "limit": 10,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    })


if __name__ == "__main__":
    main()
