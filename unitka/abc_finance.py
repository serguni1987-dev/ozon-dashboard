"""Read-only candidate financial input for ABC. Does not replace stored ABC snapshots."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

BASIS = "before tax; allocated Ozon overhead; latest cost; internal reconciliation only"
FIELDS = ("sku", "income", "units", "commission", "sku_services", "overhead", "cogs", "profit", "basis")


def _number(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid number: {label}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite number: {label}")
    return result


def _match(actual, expected, label):
    expected = _number(expected, label)
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=0.011):
        raise ValueError(f"Reconciliation failed: {label}: {actual:.4f} vs {expected:.4f}")


def prepare_rows(eco):
    """Validate current unit_core output; never repair a discrepancy by force."""
    rows = []
    seen = set()
    keys = ("income", "units", "commission", "svc_fixed", "svc_pct", "overhead",
            "cogs", "profit", "delivered", "returned", "cost_unit")
    for raw_sku, source in eco["skus"].items():
        text = str(raw_sku).strip()
        if not text.isascii() or not text.isdigit() or int(text) <= 0:
            raise ValueError(f"Invalid SKU: {raw_sku!r}")
        sku = int(text)
        if sku in seen:
            raise ValueError(f"Duplicate normalized SKU: {sku}")
        seen.add(sku)
        s = {key: _number(source[key], f"{sku}.{key}") for key in keys}
        _match(s["units"], s["delivered"] - s["returned"], f"{sku}.units")
        if (s["delivered"] != 0 or s["returned"] != 0) and s["cost_unit"] <= 0:
            raise ValueError(f"Missing positive cost: SKU {sku}")
        _match(s["cogs"], s["units"] * s["cost_unit"], f"{sku}.cogs")
        services = s["svc_fixed"] + s["svc_pct"]
        profit = s["income"] - s["commission"] - services - s["overhead"] - s["cogs"]
        _match(profit, s["profit"], f"{sku}.profit")
        if not any(s[key] != 0 for key in keys if key != "cost_unit"):
            continue
        rows.append({"sku": sku, "income": s["income"], "units": s["units"],
                     "commission": s["commission"], "sku_services": services,
                     "overhead": s["overhead"], "cogs": s["cogs"],
                     "profit": profit, "basis": BASIS})
    totals = eco["totals"]
    for field, target in (("income", "pnl_income"), ("cogs", "pnl_cogs"),
                          ("profit", "pnl_gross_profit")):
        total = math.fsum(row[field] for row in rows)
        _match(total, totals[target], target)
        _match(total, totals["gross_profit" if field == "profit" else field], field)
    return sorted(rows, key=lambda row: (-row["profit"], row["sku"]))


def build_preview(conn, dfrom, dto):
    """Dates are inclusive, matching the legacy ABC CLI; core end is exclusive."""
    start, end = date.fromisoformat(dfrom), date.fromisoformat(dto)
    if start > end:
        raise ValueError("Start date must not be after end date")
    stop = (end + timedelta(days=1)).isoformat()
    from .unit_core import sku_economics
    eco = sku_economics(conn.cursor(), start.isoformat(), stop)
    rows = prepare_rows(eco)
    return {"date_from": start.isoformat(), "date_to_inclusive": end.isoformat(),
            "basis": BASIS, "cogs_estimated": bool(eco["totals"]["cogs_estimated"]),
            "sku_count": len(rows),
            "income": math.fsum(row["income"] for row in rows),
            "cogs": math.fsum(row["cogs"] for row in rows),
            "profit": math.fsum(row["profit"] for row in rows), "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--from", dest="dfrom", required=True)
    parser.add_argument("--to", dest="dto", required=True)
    parser.add_argument("--out", required=True, help="New CSV file; will not overwrite")
    args = parser.parse_args(argv)
    source = Path(args.db).resolve()
    if not source.is_file():
        parser.error("Database does not exist")
    target = Path(args.out).resolve()
    if target == source or target.exists():
        parser.error("Output must be a new file, not the database")
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            preview = build_preview(conn, args.dfrom, args.dto)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
            writer.writeheader()
            writer.writerows(preview["rows"])
    except (ValueError, KeyError, OverflowError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"Preview failed: {exc}\n")
    summary = {key: value for key, value in preview.items() if key != "rows"}
    print(json.dumps(summary, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
