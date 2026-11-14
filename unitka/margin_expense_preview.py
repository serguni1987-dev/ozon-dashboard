"""Expense-only SKU correction candidate. Read-only preview, never publishes."""
import argparse
import contextlib
import copy
from datetime import date
import io
import json
import math
from pathlib import Path
import sqlite3


def number(value):
    value = float(value or 0)
    if not math.isfinite(value):
        raise ValueError("Non-finite financial value")
    return value


def sku_key(value):
    if isinstance(value, bool):
        raise ValueError("Invalid SKU")
    text = str(value).strip()
    if not text.isascii() or not text.isdigit() or int(text) <= 0:
        raise ValueError("Invalid SKU")
    return int(text)


def add_missing_expense_skus(con, data, start, end, service_groups):
    """Keep existing rows unchanged. Preserve legacy abs() semantics for this candidate."""
    result = copy.deepcopy(data)
    present = {sku_key(key) for key in result}
    if len(present) != len(result):
        raise ValueError("Duplicate normalized SKU keys")
    added = set()
    rows = con.execute("""
        SELECT sku, type_id, SUM(amount) AS amount
        FROM accrual_sku_daily
        WHERE date BETWEEN ? AND ?
        GROUP BY sku, type_id
    """, (start, end)).fetchall()
    for raw_sku, tid, raw_amount in rows:
        if raw_sku in (None, "", 0, "0"):
            continue
        sku = sku_key(raw_sku)
        amount = abs(number(raw_amount))
        if sku in present or not amount:
            continue
        if sku not in added:
            result[sku] = dict(sku=sku, offer_id="", name="", category="",
                orders=0, cancelled=0, returned=0, purchased=0,
                seller_price=0.0, sale_price=0.0, bonus=0.0,
                coinvestment=0.0, revenue=0.0, commission=0.0,
                logistics=0.0, agents=0.0, fbo=0.0, marketing=0.0,
                other=0.0, cogs=0.0, fbo_stock=0, fbs_stock=0)
            product = con.execute("""
                SELECT offer_id, name, category_l1 FROM products
                WHERE sku=? LIMIT 1
            """, (sku,)).fetchone()
            if product:
                result[sku].update(offer_id=product[0] or "",
                    name=product[1] or "", category=product[2] or "")
            added.add(sku)
        category = next((name for name, ids in service_groups.items() if tid in ids), "other")
        result[sku][category] += amount
    return result, sorted(added)


def profit_preview(data, ozon_total):
    direct = {key: sum(number(row.get(field)) for field in
        ("commission", "logistics", "agents", "fbo", "marketing", "other"))
        for key, row in data.items()}
    residual = number(ozon_total) - math.fsum(direct.values())
    revenue = math.fsum(max(number(row.get("revenue")), 0) for row in data.values())
    rows = []
    for key, row in data.items():
        income = number(row.get("revenue"))
        extras = residual * income / revenue if revenue > 0 and income > 0 and abs(residual) > 0.5 else 0.0
        profit = income - number(row.get("cogs")) - direct[key] - extras
        visible = (number(row.get("orders")) > 0 or number(row.get("purchased")) > 0
                   or abs(income) > 0.005 or direct[key] > 0.005)
        rows.append(dict(sku=sku_key(key), income=income,
            services=direct[key]-number(row.get("commission")),
            extras=extras, profit_before_tax=profit, included=visible))
    return dict(unallocated=residual,
        profit_before_tax=math.fsum(row["profit_before_tax"] for row in rows),
        displayed_profit_before_tax=math.fsum(row["profit_before_tax"] for row in rows if row["included"]),
        rows=rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    args = parser.parse_args(argv)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start > end or not args.db.is_file():
        parser.error("Existing database and ordered dates are required")
    from . import calc_margin, unit_core
    from datetime import timedelta
    path = args.db.resolve()
    with contextlib.closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        messages = io.StringIO()
        with contextlib.redirect_stdout(messages):
            original = calc_margin.load_period(con, args.start, args.end, {})
            core = unit_core.sku_economics(con.cursor(), args.start, (end+timedelta(days=1)).isoformat())
        if "Сверка с отчётом о реализации не выполнена" in messages.getvalue():
            raise ValueError("Source calculation reconciliation failed")
        candidate, added = add_missing_expense_skus(con, original, args.start, args.end, calc_margin.SERVICE_GROUPS)
        before = profit_preview(original, core["totals"]["ozon_total"])
        after = profit_preview(candidate, core["totals"]["ozon_total"])
        report = dict(preview_only=True, can_publish=False,
            period=[args.start,args.end], messages=messages.getvalue(), added_skus=added,
            before=before, candidate=after,
            candidate_minus_before_profit=after["profit_before_tax"]-before["profit_before_tax"],
            core_profit_before_tax=core["totals"]["gross_profit"],
            unchanged="No tax, price, fine attribution or sign-policy changes; no DB or Sheets writes")
    print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
