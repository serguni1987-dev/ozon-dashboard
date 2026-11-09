"""Загрузка дневной реализации из /v1/finance/accrual/by-day."""
import argparse
import json
import re
from datetime import date, datetime, timedelta

from . import config, db
from .ozon_client import OzonClient

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    p.add_argument("--to",   dest="date_to",   help="YYYY-MM-DD")
    p.add_argument("--date", dest="single",    help="один день YYYY-MM-DD")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def next_date(con):
    row = con.execute(
        "SELECT MAX(date) AS m FROM load_log WHERE status='ok'").fetchone()
    if not row or not row["m"]:
        return None
    return datetime.strptime(row["m"], "%Y-%m-%d").date() + timedelta(days=1)


def _f(x) -> float:
    """Достаёт число из любого формата Ozon.

    Возможные варианты:
      {"amount": "0.49", "currency": "RUB"}
      {"amount": 'value:"0.490000"'}
      'value:"0.490000"'
      "0.49"
      0.49
      None
    """
    if x is None:
        return 0.0
    if isinstance(x, dict):
        for key in ("amount", "value", "total", "total_accrued"):
            if key in x:
                return _f(x[key])
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    # быстрый путь — просто число
    try:
        return float(s)
    except ValueError:
        pass
    # общий путь — первое число в строке
    m = _NUM_RE.search(s)
    if not m:
        return 0.0
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return 0.0


def _posting_number(acc):
    posting = acc.get("posting") or {}
    return acc.get("unit_number") or posting.get("posting_number")


def process_accrual(con, day, acc, now_iso):
    n_real = n_sku = n_non = 0
    accrual_id = acc.get("accrual_id")
    posting_number = _posting_number(acc)
    posting = acc.get("posting") or {}

    for prod in posting.get("products") or []:
        sku = prod.get("sku")
        if not sku:
            continue
        comm = prod.get("commission") or {}
        delivery = prod.get("delivery") or {}

        sale_price_u   = _f(comm.get("sale_price"))
        seller_price_u = _f(comm.get("seller_price"))
        sale_amount    = _f(comm.get("sale_amount"))
        commission     = _f(comm.get("commission"))

        qty = int(prod.get("quantity") or 1)

        services = delivery.get("services") or []
        del_total = sum(_f(s.get("accrued")) for s in services) or _f(delivery.get("total_accrued"))

        con.execute("""
            INSERT OR REPLACE INTO realization_daily
            (date, accrual_id, posting_number, sku, offer_id, quantity,
             seller_price, sale_price, sale_amount, bonus, coinvestment,
             commission, commission_ratio, delivery_total, is_return,
             raw_json, fetched_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (day, accrual_id, posting_number, int(sku), qty,
              seller_price_u, sale_price_u, sale_amount,
              _f(comm.get("bonus")), _f(comm.get("coinvestment")),
              commission, _f(comm.get("commission_ratio")),
              del_total, json.dumps(prod, ensure_ascii=False), now_iso))
        n_real += 1

        for s in services:
            tid = int(s.get("type_id") or 0)
            amt = _f(s.get("accrued"))
            if tid and amt:
                con.execute("""
                    INSERT OR REPLACE INTO accrual_sku_daily
                    (date, accrual_id, posting_number, sku, type_id, amount, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (day, accrual_id, posting_number, int(sku), tid, amt,
                      json.dumps(s, ensure_ascii=False), now_iso))
                n_sku += 1

    for sku_fee in (acc.get("item_fees") or {}).get("fees") or []:
        sku = sku_fee.get("sku")
        if not sku:
            continue
        for fee in sku_fee.get("fees") or []:
            tid = int(fee.get("type_id") or 0)
            amt = _f(fee.get("accrued"))
            if tid and amt:
                con.execute("""
                    INSERT OR REPLACE INTO accrual_sku_daily
                    (date, accrual_id, posting_number, sku, type_id, amount, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (day, accrual_id, posting_number, int(sku), tid, amt,
                      json.dumps(fee, ensure_ascii=False), now_iso))
                n_sku += 1

    for fee in (acc.get("container_fees") or {}).get("fees") or []:
        tid = int(fee.get("type_id") or 0)
        amt = _f(fee.get("accrued"))
        if tid and amt:
            con.execute("""
                INSERT OR REPLACE INTO accrual_non_item_daily
                (date, accrual_id, posting_number, type_id, amount, kind, raw_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, 'container', ?, ?)
            """, (day, accrual_id, posting_number, tid, amt,
                  json.dumps(fee, ensure_ascii=False), now_iso))
            n_non += 1

    ni = acc.get("non_item_fee") or {}
    if ni:
        tid = int(ni.get("type_id") or 0)
        amt = _f(ni.get("accrued"))
        if tid and amt:
            con.execute("""
                INSERT OR REPLACE INTO accrual_non_item_daily
                (date, accrual_id, posting_number, type_id, amount, kind, raw_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, 'non_item', ?, ?)
            """, (day, accrual_id, posting_number, tid, amt,
                  json.dumps(ni, ensure_ascii=False), now_iso))
            n_non += 1

    return n_real, n_sku, n_non


def load_day(client, con, day, force=False):
    now_iso = datetime.now().isoformat(timespec="seconds")
    if not force:
        row = con.execute("SELECT status FROM load_log WHERE date=?", (day,)).fetchone()
        if row and row["status"] == "ok":
            return {"date": day, "skipped": True}
    try:
        accruals = client.accrual_by_day_all(day)
        n_real = n_sku = n_non = 0
        for acc in accruals:
            r, s, n = process_accrual(con, day, acc, now_iso)
            n_real += r; n_sku += s; n_non += n
        con.execute("""
            INSERT OR REPLACE INTO load_log
            (date, status, n_accruals, n_rows, error, fetched_at)
            VALUES (?, 'ok', ?, ?, NULL, ?)
        """, (day, len(accruals), n_real, now_iso))
        con.commit()
        return {"date": day, "accruals": len(accruals),
                "real_rows": n_real, "sku_fees": n_sku, "non_item": n_non}
    except Exception as e:
        con.execute("""
            INSERT OR REPLACE INTO load_log
            (date, status, n_accruals, n_rows, error, fetched_at)
            VALUES (?, 'error', 0, 0, ?, ?)
        """, (day, str(e), now_iso))
        con.commit()
        return {"date": day, "error": str(e)}


def main():
    args = parse_args()
    config.check_credentials()
    client = OzonClient()
    con = db.connect()
    db.init_schema(con)

    if args.single:
        d1 = d2 = datetime.strptime(args.single, "%Y-%m-%d").date()
    elif args.date_from and args.date_to:
        d1 = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        d2 = datetime.strptime(args.date_to,   "%Y-%m-%d").date()
    else:
        d1 = next_date(con) or date.today()
        d2 = date.today()

    print(f"Диапазон: {d1} .. {d2}")
    for d in daterange(d1, d2):
        s = d.strftime("%Y-%m-%d")
        print(f"  {s}: {load_day(client, con, s, force=args.force)}")


if __name__ == "__main__":
    main()
