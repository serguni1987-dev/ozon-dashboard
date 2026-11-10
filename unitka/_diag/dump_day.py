"""Дамп одного дня из API в JSON."""
import json
import sys
from pathlib import Path

from .. import config
from ..ozon_client import OzonClient


def main():
    if len(sys.argv) < 2:
        print("Укажи дату: py -m unitka._diag.dump_day 2026-08-15")
        return
    day = sys.argv[1]
    config.check_credentials()
    client = OzonClient()
    accruals = client.accrual_by_day_all(day)
    out = config.PROJECT / f"dump_{day}.json"
    out.write_text(json.dumps(accruals, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"Записей: {len(accruals)}, файл: {out}")


if __name__ == "__main__":
    main()
