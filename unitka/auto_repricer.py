"""Price planning only. Live repricing is blocked pending financial audit."""
from __future__ import annotations

import argparse
import logging
import math
from datetime import date, timedelta

log = logging.getLogger(__name__)


def _positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def build_tasks(floors, sku_to_offer, real_prices, limit=0):
    """Build a preview, never an instruction that may be sent automatically."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    mapped = {}
    for sku, offer in sku_to_offer.items():
        if offer:
            mapped.setdefault(str(offer), []).append(sku)
    tasks = []
    for sku, floor in floors.items():
        offer = sku_to_offer.get(sku)
        if not offer or len(mapped.get(str(offer), [])) != 1:
            continue
        current = _positive(real_prices.get(offer))
        minimum = _positive(floor.get("min_direct"))
        if current is None or minimum is None or current >= minimum:
            continue
        new = round(min(minimum * 1.02, current * 1.15), 2)
        if not math.isfinite(new) or new <= current:
            continue
        tasks.append({"offer_id": offer, "old": current, "new": new,
                      "min_direct": minimum, "still_below_floor": new < minimum})
    tasks.sort(key=lambda item: (item["old"], str(item["offer_id"])))
    return tasks[:limit] if limit else tasks


def get_real_prices(client, offer_ids):
    """Read prices; errors abort the preview instead of using partial results."""
    prices = {}
    offers = list(dict.fromkeys(offer_ids))
    for offset in range(0, len(offers), 1000):
        chunk = offers[offset:offset + 1000]
        data = client._post("/v5/product/info/prices", {
            "filter": {"offer_id": chunk}, "limit": len(chunk), "cursor": ""})
        items = data.get("items")
        if not isinstance(items, list):
            raise ValueError("Invalid price response: items must be a list")
        if data.get("has_next") or data.get("cursor"):
            raise ValueError("Incomplete price response: pagination needs review")
        for item in items:
            offer = item.get("offer_id")
            price = _positive((item.get("price") or {}).get("price"))
            if offer in chunk and price is not None:
                if offer in prices:
                    raise ValueError("Duplicate offer in price response")
                prices[offer] = price
    return prices


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Preview (default)")
    modes.add_argument("--apply", action="store_true", help="Blocked pending audit")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.apply:
        parser.error("Live repricing is BLOCKED pending financial audit; use --dry-run")

    # No optional dependency, DB or API is touched before the safety gate above.
    import gspread
    from google.oauth2.service_account import Credentials
    from . import config, settings, unit_core
    from .db import connect
    from .finance_core import tax_settings
    from .ozon_client import OzonClient

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=scopes)
    sheet = gspread.authorize(credentials).open_by_key(config.SHEET_ID)
    today = date.today()
    conn = connect()
    try:
        cur = conn.cursor()
        eco = unit_core.sku_economics(cur, f"{today.year}-01-01", (today + timedelta(days=1)).isoformat())
        floors = unit_core.min_prices(cur, eco, tax_settings(sheet), settings.unit_params(sheet))
        rows = cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''").fetchall()
        sku_to_offer = {}
        for sku, offer in rows:
            sku = int(sku)
            if sku in sku_to_offer and sku_to_offer[sku] != offer:
                raise ValueError("Ambiguous SKU mapping")
            sku_to_offer[sku] = offer
        prices = get_real_prices(OzonClient(), list(sku_to_offer.values()))
        tasks = build_tasks(floors, sku_to_offer, prices, args.limit)
        log.warning("PREVIEW ONLY: financial inputs are not yet fully audited; live writes blocked")
        for task in tasks:
            log.info("%s: %.2f -> %.2f; floor %.2f; remains below floor: %s",
                     task["offer_id"], task["old"], task["new"],
                     task["min_direct"], task["still_below_floor"])
        log.info("Preview tasks: %s; prices sent: 0", len(tasks))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    raise SystemExit(main())
