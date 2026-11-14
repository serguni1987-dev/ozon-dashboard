"""Fetch a complete price snapshot, validate it, then replace rows atomically.

This module never calls the Ozon price-update endpoint.
The legacy column sku continues to store product_id, not marketplace SKU.
"""
import argparse
import json
import hashlib
import math
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

URL = "https://api-seller.ozon.ru/v5/product/info/prices"
PAGE_SIZE = 1000
COLUMNS = ("offer_id", "sku", "price", "old_price", "min_price", "marketing_price",
           "net_price", "currency", "acquiring", "sales_percent_fbo", "sales_percent_fbs",
           "price_index_color", "price_index_value", "price_index_min", "volume_weight", "fetched_at")
CREATE_SQL = """CREATE TABLE IF NOT EXISTS current_prices (
    offer_id TEXT PRIMARY KEY, sku INTEGER, price REAL, old_price REAL, min_price REAL,
    marketing_price REAL, net_price REAL, currency TEXT, acquiring REAL,
    sales_percent_fbo REAL, sales_percent_fbs REAL, price_index_color TEXT,
    price_index_value REAL, price_index_min REAL, volume_weight REAL, fetched_at TEXT)"""


class PriceLoadError(ValueError):
    pass


def _config():
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from unitka import config
    return config


def tf(value):
    """Missing stays None; valid zero stays zero; malformed/nonfinite fails."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise PriceLoadError("Boolean where a number was expected")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PriceLoadError("Invalid numeric field") from exc
    if not math.isfinite(result) or result < 0:
        raise PriceLoadError("Negative or non-finite numeric field")
    return result


def _count(value):
    if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit():
        raise PriceLoadError("Invalid integer count or product_id")
    result = int(value)
    if result > 9223372036854775807:
        raise PriceLoadError("Integer exceeds SQLite range")
    return result


def _object(value, field):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PriceLoadError("Expected object: " + field)
    return value


def parse_item(item, fetched_at):
    if not isinstance(item, dict):
        raise PriceLoadError("Invalid price item")
    offer = item.get("offer_id")
    if not isinstance(offer, str) or not offer.strip() or offer != offer.strip():
        raise PriceLoadError("Invalid offer_id")
    product_id = _count(item.get("product_id"))
    if product_id == 0:
        raise PriceLoadError("Missing positive product_id")
    p = _object(item.get("price"), "price")
    currency = p.get("currency_code")
    if not isinstance(currency, str) or not currency.strip():
        raise PriceLoadError("Missing currency_code")
    comm = _object(item.get("commissions"), "commissions")
    fbo, fbs = tf(comm.get("sales_percent_fbo")), tf(comm.get("sales_percent_fbs"))
    if any(value is not None and value > 100 for value in (fbo, fbs)):
        raise PriceLoadError("Commission percentage exceeds 100")
    index = _object(item.get("price_indexes"), "price_indexes")
    ozon_index = _object(index.get("ozon_index_data"), "ozon_index_data")
    color = index.get("color_index") or ""
    if not isinstance(color, str):
        raise PriceLoadError("Invalid index color")
    return (offer, product_id, tf(p.get("price")), tf(p.get("old_price")), tf(p.get("min_price")),
        tf(p.get("marketing_seller_price")), tf(p.get("net_price")), currency,
        tf(item.get("acquiring")), fbo, fbs, color, tf(ozon_index.get("price_index_value")),
        tf(ozon_index.get("min_price")), tf(item.get("volume_weight")), fetched_at)


def fetch_page(cursor="", post=None, headers=None, url=URL):
    if headers is None:
        config = _config()
        config.check_credentials()
        headers = {"Client-Id": config.OZON_CLIENT_ID, "Api-Key": config.OZON_API_KEY,
                   "Content-Type": "application/json"}
    if post is None:
        import requests
        post = requests.post
    try:
        response = post(url, headers=headers, json={"filter": {"visibility": "ALL"},
            "cursor": cursor, "limit": PAGE_SIZE}, timeout=60)
        if response.status_code != 200:
            raise PriceLoadError(f"HTTP {response.status_code}")
        data = response.json()
    except PriceLoadError:
        raise
    except Exception as exc:
        raise PriceLoadError("Request or JSON failure: " + type(exc).__name__) from exc
    if not isinstance(data, dict):
        raise PriceLoadError("Response must be an object")
    return data


def collect_rows(fetcher, max_pages=100):
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise PriceLoadError("max_pages must be a positive integer")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor, expected = "", None
    seen_cursors, offers, products, rows = set(), set(), set(), []
    for page in range(1, max_pages + 1):
        if cursor in seen_cursors:
            raise PriceLoadError("Repeated pagination cursor")
        seen_cursors.add(cursor)
        data = fetcher(cursor)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise PriceLoadError("Missing items array")
        items = data["items"]
        if len(items) > PAGE_SIZE:
            raise PriceLoadError("Page exceeds requested limit")
        total = data.get("total_items")
        if total is None:
            total = data.get("total")
        if total is not None:
            total = _count(total)
            if expected is not None and total != expected:
                raise PriceLoadError("Declared total changed during pagination")
            expected = total
        next_cursor = data.get("cursor")
        if next_cursor is None:
            next_cursor = ""
        if not isinstance(next_cursor, str):
            raise PriceLoadError("Invalid cursor")
        for item in items:
            row = parse_item(item, stamp)
            if row[0] in offers:
                raise PriceLoadError("Duplicate or conflicting offer_id across pages")
            if row[1] in products:
                raise PriceLoadError("Conflicting product_id across offers")
            offers.add(row[0]); products.add(row[1]); rows.append(row)
        if expected is not None and len(rows) > expected:
            raise PriceLoadError("Received more rows than declared")
        if items and next_cursor and next_cursor in seen_cursors:
            raise PriceLoadError("Repeated pagination cursor")
        if not items or not next_cursor or (expected is not None and len(rows) == expected):
            if data.get("has_next") is True:
                raise PriceLoadError("Contradictory pagination marker")
            if expected is not None and len(rows) != expected:
                raise PriceLoadError("Incomplete snapshot: count mismatch")
            if expected is None and len(items) == PAGE_SIZE and not next_cursor:
                raise PriceLoadError("Full page without cursor or count cannot prove completion")
            if not rows or not any(row[2] is not None and row[2] > 0 for row in rows):
                raise PriceLoadError("Empty or entirely unpriced snapshot rejected")
            return rows, {"pages": page, "declared_total": expected,
                          "count_verified": expected is not None}
        if next_cursor in seen_cursors:
            raise PriceLoadError("Repeated pagination cursor")
        cursor = next_cursor
    raise PriceLoadError("Page limit reached before completion")


_UNSET = object()


def _signature(con):
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='current_prices'").fetchone()
    if not exists:
        return None
    columns = [r[1] for r in con.execute("PRAGMA table_info(current_prices)")]
    records = [tuple(r) for r in con.execute("SELECT * FROM current_prices ORDER BY offer_id")]
    value = json.dumps([columns, records], ensure_ascii=True, default=repr, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _replace_snapshot(con, rows, allow_large_drop=False, expected_signature=_UNSET):
    """Only normalized rows from collect_rows; no executescript/implicit commit."""
    if con.in_transaction:
        raise PriceLoadError("Refusing to commit a caller-owned transaction")
    try:
        con.execute("BEGIN IMMEDIATE")
        if expected_signature is not _UNSET and _signature(con) != expected_signature:
            raise PriceLoadError("Price snapshot changed during fetch; retry instead of overwriting")
        con.execute(CREATE_SQL)
        actual = tuple(r[1] for r in con.execute("PRAGMA table_info(current_prices)"))
        if set(actual) != set(COLUMNS):
            raise PriceLoadError("Unexpected schema; explicit migration required")
        previous = con.execute("SELECT COUNT(*) FROM current_prices").fetchone()[0]
        if not allow_large_drop and len(rows) < previous * 0.8:
            raise PriceLoadError("Row count dropped by more than 20%; review before --allow-large-drop")
        con.execute("DELETE FROM current_prices")
        marks = ",".join("?" for _ in COLUMNS)
        con.executemany(f"INSERT INTO current_prices ({','.join(COLUMNS)}) VALUES ({marks})", rows)
        con.execute("CREATE INDEX IF NOT EXISTS idx_cp_sku ON current_prices(sku)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cp_color ON current_prices(price_index_color)")
        con.commit()
    except BaseException:
        con.rollback()
        raise


def refresh_prices(con, fetcher, max_pages=100, allow_large_drop=False):
    if con.in_transaction:
        raise PriceLoadError("Refusing a caller-owned transaction")
    signature = _signature(con)
    rows, details = collect_rows(fetcher, max_pages)
    _replace_snapshot(con, rows, allow_large_drop, expected_signature=signature)
    return {"status": "OK", "rows": len(rows), "fetched_at": rows[0][-1], **details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--allow-large-drop", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate only; no DB changes")
    args = parser.parse_args(argv)
    config = _config()
    path = Path(args.db or config.DB_PATH).resolve()
    if not path.is_file():
        parser.error("Database does not exist; no file will be created")
    try:
        config.check_credentials()
        headers = {"Client-Id": config.OZON_CLIENT_ID, "Api-Key": config.OZON_API_KEY,
                   "Content-Type": "application/json"}
        url = config.OZON_BASE_URL.rstrip("/") + "/v5/product/info/prices"
        fetcher = lambda cursor: fetch_page(cursor, headers=headers, url=url)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as existing:
            signature = _signature(existing)
        rows, details = collect_rows(fetcher, args.max_pages)
        if args.dry_run:
            summary = {"status": "VALIDATED_ONLY", "rows": len(rows), **details}
        else:
            with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30)) as con:
                _replace_snapshot(con, rows, args.allow_large_drop, expected_signature=signature)
            summary = {"status": "OK", "rows": len(rows), "fetched_at": rows[0][-1], **details}
    except (PriceLoadError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"Price refresh failed: {exc}\n")
    print(json.dumps(summary, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
