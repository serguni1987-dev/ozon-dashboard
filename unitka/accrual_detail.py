"""Read item-level accruals without duplicating operation-level net amounts."""
from __future__ import annotations
import json
import math
import sqlite3

FIELDS = ("seller_price", "sale_price", "sale_commission", "bonus", "coinvestment")

def number(value):
    if isinstance(value, dict):
        value = value.get("amount")
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        raise ValueError("Boolean financial amount")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite financial amount")
    return result

def sku_key(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return str(value)

def product_rows(acc):
    posting = acc.get("posting") or {}
    if not isinstance(posting, dict):
        raise ValueError("Invalid posting")
    products = posting.get("products") or []
    if not isinstance(products, list):
        raise ValueError("Invalid products")
    out = []
    for p in products:
        if not isinstance(p, dict):
            raise ValueError("Invalid product")
        comm = p.get("commission") or {}
        if not isinstance(comm, dict):
            raise ValueError("Invalid commission")
        quantity = number(p.get("quantity", 1))
        if quantity <= 0 or quantity != int(quantity):
            raise ValueError("Invalid product quantity")
        row = {key: number(comm.get(key)) for key in FIELDS}
        if comm.get("sale_commission") is None:
            row["sale_commission"] = number(comm.get("commission"))
        row.update(sku=sku_key(p.get("sku")), quantity=int(quantity))
        if row["sku"] is None and any(row[k] for k in FIELDS):
            raise ValueError("Financial product has no SKU")
        out.append(row)
    return out

def iter_accrual_products(cur, date_from, date_to):
    """Read full JSON detail, supporting the existing minimal flat schema."""
    cur.execute('PRAGMA table_info("accruals")')
    columns = {row[1] for row in cur.fetchall()}
    required = {"sku", "sale_price", "sale_commission", "bonus", "coinvestment",
                "accrued_category", "date"}
    missing = required - columns
    if missing:
        raise ValueError("accruals missing required columns: " + ", ".join(sorted(missing)))
    seller_sql = "seller_price" if "seller_price" in columns else "NULL AS seller_price"
    raw_sql = "raw_json" if "raw_json" in columns else "NULL AS raw_json"
    order_sql = "date, accrual_id" if "accrual_id" in columns else "date, sku"
    cur.execute(f"""SELECT sku, {seller_sql}, sale_price, sale_commission,
        bonus, coinvestment, accrued_category, date, {raw_sql}
        FROM accruals WHERE date >= ? AND date < ? ORDER BY {order_sql}""",
        (date_from, date_to))
    records = cur.fetchall()
    for sku, seller, price, commission, bonus, coinv, category, day, raw in records:
        if raw:
            acc = json.loads(raw)
            if not isinstance(acc, dict):
                raise ValueError("Invalid accrual JSON")
            posting = acc.get("posting")
            authoritative = isinstance(posting, dict) and "products" in posting
            rows = product_rows(acc) if authoritative else None
        else:
            rows = None
        if rows is None:
            rows = [dict(zip(FIELDS, map(number, (seller, price, commission, bonus, coinv))))]
            rows[0].update(sku=sku_key(sku), quantity=1)
        for row in rows:
            yield dict(row, date=day, accrued_category=category)

def _services(acc, types):
    out = []
    def add(sku, fee):
        if not isinstance(fee, dict):
            raise ValueError("Invalid service")
        tid = fee.get("type_id")
        amount = fee.get("accrued")
        if tid is None or amount is None:
            return
        out.append((sku_key(sku), tid, types.get(tid, f"type_{tid}"), number(amount)))
    posting = acc.get("posting") or {}
    for p in posting.get("products") or []:
        for fee in (p.get("delivery") or {}).get("services") or []:
            add(p.get("sku"), fee)
    ni = acc.get("non_item_fee")
    if ni:
        add(None, ni)
    for group in (acc.get("item_fees") or {}).get("fees") or []:
        for fee in group.get("fees") or []:
            add(group.get("sku"), fee)
    for fee in (acc.get("container_fees") or {}).get("fees") or []:
        add(None, fee)
    if not out and not (posting.get("products") or []):
        total = number(acc.get("total_amount"))
        if total:
            out.append((None, 0, acc.get("accrued_category") or "UNKNOWN", total))
    return out

def save_accrual_record(cur, acc, types):
    """One header per operation; detail stays lossless in raw_json.

    Caller owns commit/rollback. Re-saving replaces only this operation's services.
    No schema changes and no historical backfill are performed.
    """
    if not isinstance(acc, dict) or not acc.get("accrual_id") or not acc.get("date"):
        raise ValueError("Missing accrual ID or date")
    items = product_rows(acc)
    services = _services(acc, types)
    total = number(acc.get("total_amount"))
    posting = acc.get("posting") or {}
    skus = {row["sku"] for row in items}
    sku = next(iter(skus)) if len(skus) == 1 else None
    sums = [sum(row[k] for row in items) if items else None for k in FIELDS]
    raw = json.dumps(acc, ensure_ascii=False, allow_nan=False)
    params = (acc["accrual_id"], acc["date"], sku, acc.get("unit_number"),
              acc.get("accrued_category"), posting.get("delivery_schema"),
              *sums, total, raw)
    con = cur.connection
    if not con.in_transaction:
        con.execute("BEGIN")
    cur.execute("SAVEPOINT save_accrual_detail")
    try:
        cur.execute("""INSERT INTO accruals
            (accrual_id,date,sku,unit_number,accrued_category,delivery_schema,
             seller_price,sale_price,sale_commission,bonus,coinvestment,total_amount,raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(accrual_id) DO UPDATE SET
              date=excluded.date,sku=excluded.sku,unit_number=excluded.unit_number,
              accrued_category=excluded.accrued_category,delivery_schema=excluded.delivery_schema,
              seller_price=excluded.seller_price,sale_price=excluded.sale_price,
              sale_commission=excluded.sale_commission,bonus=excluded.bonus,
              coinvestment=excluded.coinvestment,total_amount=excluded.total_amount,
              raw_json=excluded.raw_json""", params)
        cur.execute("DELETE FROM accruals_services WHERE accrual_id=?", (acc["accrual_id"],))
        cur.executemany("""INSERT INTO accruals_services
            (accrual_id,date,sku,type_id,type_name,amount) VALUES (?,?,?,?,?,?)""",
            [(acc["accrual_id"], acc["date"], *row) for row in services])
    except Exception:
        cur.execute("ROLLBACK TO save_accrual_detail")
        cur.execute("RELEASE save_accrual_detail")
        raise
    cur.execute("RELEASE save_accrual_detail")
    return 1, len(services)
