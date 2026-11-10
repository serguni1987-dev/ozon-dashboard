"""Дамп одного дня из /v3/posting/fbs/list."""
import json
import sys
from pathlib import Path
from .. import config
from ..ozon_client import OzonClient


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else "2026-09-15"
    config.check_credentials()
    client = OzonClient()

    # фильтр: created_at за день (от 00:00 до 23:59:59)
    payload = {
        "dir": "ASC",
        "filter": {
            "since": day + "T00:00:00Z",
            "to":   day + "T23:59:59Z",
        },
        "limit": 100,
        "offset": 0,
        "with": {"analytics_data": True, "financial_data": True}
    }
    # Ozon требует конкретный метод — FBS или FBO. Пробуем FBS.
    resp = client._post("/v3/posting/fbs/list", payload)
    postings = resp.get("postings") or []
    print(f"FBS за {day}: {len(postings)} отправлений, has_next={resp.get('has_next')}")

    out = Path(r"C:\Users\sergu\Desktop\проект") / f"dump_postings_fbs_{day}.json"
    out.write_text(json.dumps(postings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Файл: {out}")

    # Покажем первое отправление целиком
    if postings:
        print("--- первое отправление ---")
        print(json.dumps(postings[0], ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main()
