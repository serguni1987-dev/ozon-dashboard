"""Minimum-price protection preview. Live writes are blocked pending financial audit."""
from __future__ import annotations

import argparse
import logging
import math
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def _positive(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def get_real_prices(client, offer_ids):
    from .auto_repricer import get_real_prices as read_prices
    return read_prices(client, offer_ids)


def build_tasks(floors, sku_to_offer, real_prices):
    """Read-only candidate floor plan, not a payload authorized for the API."""
    counts = Counter(str(offer) for offer in sku_to_offer.values() if offer)
    tasks = []
    for sku, floor in floors.items():
        offer = sku_to_offer.get(sku)
        if not offer or counts[str(offer)] != 1:
            continue
        minimum = _positive(floor.get("min_direct"))
        current = _positive(real_prices.get(offer))
        if minimum is None or current is None or current < minimum:
            continue
        minimum, current = round(minimum, 2), round(current, 2)
        if minimum <= 0 or minimum > current:
            continue
        tasks.append({"offer_id": offer, "min_price": minimum, "current_price": current})
    return sorted(tasks, key=lambda task: str(task["offer_id"]))


def _preview(limit):
    import gspread
    from google.oauth2.service_account import Credentials
    from . import config, settings, unit_core
    from .finance_core import tax_settings
    from .ozon_client import OzonClient

    path = Path(config.DB_PATH).resolve()
    if not path.is_file():
        raise ValueError("Database does not exist")
    credentials = Credentials.from_service_account_file(str(config.CREDENTIALS),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    sheet = gspread.authorize(credentials).open_by_key(config.SHEET_ID)
    today = date.today()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        cur = conn.cursor()
        eco = unit_core.sku_economics(cur, f"{today.year}-01-01", (today + timedelta(days=1)).isoformat())
        floors = unit_core.min_prices(cur, eco, tax_settings(sheet), settings.unit_params(sheet))
        mapping = {}
        for sku, offer in cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''"):
            sku = int(sku)
            if sku in mapping and mapping[sku] != offer:
                raise ValueError("Ambiguous SKU mapping")
            mapping[sku] = offer
    prices = get_real_prices(OzonClient(), list(mapping.values()))
    tasks = build_tasks(floors, mapping, prices)
    log.warning("PREVIEW ONLY: min-price and auto-action writes are BLOCKED; model floors are not approved")
    for task in tasks[:limit] if limit else tasks:
        log.info("%s: current %.2f; candidate floor %.2f; NOT SENT",
                 task["offer_id"], task["current_price"], task["min_price"])
    log.info("Candidate tasks: %s; requests to change prices or protection: 0", len(tasks))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Preview (default)")
    modes.add_argument("--apply", action="store_true", help="Blocked pending audit")
    parser.add_argument("--limit", type=int, default=10, help="Preview rows; 0 means all")
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.apply:
        parser.error("Live minimum-price and auto-action writes are BLOCKED pending audit")
    return _preview(args.limit)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    raise SystemExit(main())
