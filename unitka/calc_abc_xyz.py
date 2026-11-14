"""Reconciled ABC/XYZ candidate. Local preview only; publishing is blocked."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .abc_finance import BASIS, build_preview

MODEL_VERSION = "abc_unit_core_preview_v1"
DEFAULT_SETTINGS = {"top_n": 10, "cz_capital": 100000.0, "cv_threshold": 25.0,
                    "cz_min": 5, "min_active_months": 3}
ABC_THRESHOLDS = (0.80, 0.95)
XYZ_THRESHOLDS = (10.0, 25.0)
OUT_DIR = Path(__file__).resolve().parent.parent / "out"
HEADER_FULL = ["SKU", "ABC", "XYZ", "Матрица", "Доход", "Прибыль до налога", "Нетто шт.",
               "Доля положительной прибыли, %", "Накопленная доля, %",
               "Активных полных месяцев", "CV доставок, %", "Капитал", "Рекомендация"]


def _cv(values):
    if len(values) < 2:
        return None
    numbers = [float(v) for v in values]
    if any(not math.isfinite(v) or v < 0 for v in numbers):
        raise ValueError("Invalid delivery quantities for XYZ")
    mean = math.fsum(numbers) / len(numbers)
    if mean <= 0:
        return None
    variance = math.fsum((v - mean) ** 2 for v in numbers) / len(numbers)
    return round(math.sqrt(variance) / mean * 100, 1)


def _classify_abc(profit_sorted):
    """Positive contributions only; threshold-crossing item stays in its starting band."""
    ordered = sorted(profit_sorted, key=lambda item: (-item[1], item[0]))
    if any(not math.isfinite(float(p)) for _, p in ordered):
        raise ValueError("Invalid profit for ABC")
    total = math.fsum(max(p, 0) for _, p in ordered)
    result, cumulative = {}, 0.0
    for sku, profit in ordered:
        share = max(profit, 0) / total if total > 0 else 0
        group = "C"
        if profit > 0:
            group = "A" if cumulative < ABC_THRESHOLDS[0] else ("B" if cumulative < ABC_THRESHOLDS[1] else "C")
        cumulative += share
        result[sku] = (group, round(share * 100, 2), round(cumulative * 100, 2))
    return result


def _classify_xyz(cv, active_months, min_active, cv_threshold):
    if active_months < min_active:
        return "N/A", "Мало истории"
    if cv is None:
        return "N/A", "Нет вариационного ряда"
    if cv <= XYZ_THRESHOLDS[0]:
        return "X", None
    if cv <= max(XYZ_THRESHOLDS[1], cv_threshold):
        return "Y", None
    return "Z", None


def _load_active_months(conn, dfrom, dto):
    """Delivered units from the same core; only complete calendar months."""
    from .finance_core import _month_bounds
    from .unit_core import sku_economics
    stop = (date.fromisoformat(dto) + timedelta(days=1)).isoformat()
    months = _month_bounds(dfrom, stop)
    result = {}
    for month, start, end in months:
        eco = sku_economics(conn.cursor(), start, end)
        for sku, source in eco["skus"].items():
            qty = float(source["delivered"])
            if not math.isfinite(qty) or qty < 0:
                raise ValueError("Invalid delivered quantity")
            if qty > 0:
                result.setdefault(int(sku), {})[month] = qty
    return {sku: {month: values.get(month, 0.0) for month, _, _ in months}
            for sku, values in result.items()}


def _load_capital(conn):
    try:
        last = conn.execute("SELECT MAX(date) FROM stock_daily").fetchone()[0]
        if last is None:
            return {}, False
        rows = conn.execute("""
            SELECT s.sku, SUM((COALESCE(s.fbo_present,0)+COALESCE(s.fbs_present,0))*
                COALESCE((SELECT c.cost_price FROM product_cost_history c
                    WHERE c.sku=s.sku AND c.date_from<=s.date
                    ORDER BY c.date_from DESC LIMIT 1),0))
            FROM stock_daily s WHERE s.date=? GROUP BY s.sku
        """, (last,)).fetchall()
    except sqlite3.OperationalError:
        return {}, False
    capital = {int(sku):float(value or 0) for sku,value in rows}
    if any(not math.isfinite(v) for v in capital.values()):
        raise ValueError("Invalid capital")
    return capital, any(v > 0 for v in capital.values())


def compute_from_connection(conn, dfrom, dto, settings=None):
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    if int(settings["min_active_months"]) < 1:
        raise ValueError("min_active_months must be positive")
    preview = build_preview(conn, dfrom, dto)
    active = _load_active_months(conn, dfrom, dto)
    capital, cap_available = _load_capital(conn)
    classified = _classify_abc([(row["sku"],row["profit"]) for row in preview["rows"]])
    items = []
    for row in preview["rows"]:
        sku = row["sku"]
        months = active.get(sku, {})
        active_count = sum(v > 0 for v in months.values())
        cv = _cv(list(months.values()))
        xyz, reason = _classify_xyz(cv,active_count,int(settings["min_active_months"]),float(settings["cv_threshold"]))
        abc, share, cumulative = classified[sku]
        matrix = abc + xyz if xyz != "N/A" else "N/A"
        recommendation = "Проверить спрос, расходы и остатки перед решением; автозакупка не разрешена."
        if row["profit"] <= 0:
            recommendation = "Прибыль неположительная: проверить экономику; не использовать класс как основание закупки."
        elif xyz == "N/A":
            recommendation = "Мало истории: наблюдать; класс не является основанием закупки."
        items.append({"sku":sku,"abc":abc,"xyz":xyz,"matrix":matrix,
            "revenue":row["income"],"profit":row["profit"],"qty":row["units"],
            "share":share,"cum":cumulative,"active_months":active_count,"cv":cv,
            "capital":capital.get(sku,0.0),"recommendation":recommendation,"reason":reason})
    total_profit = math.fsum(i["profit"] for i in items)
    if not math.isclose(total_profit,preview["profit"],abs_tol=0.011,rel_tol=0):
        raise ValueError("ABC profit does not reconcile")
    matrix = {a:{x:[] for x in ("X","Y","Z","N/A")} for a in "ABC"}
    for item in items:
        matrix[item["abc"]][item["xyz"]].append(item)
    return {"period":f"{dfrom}_{dto}","dfrom":dfrom,"dto":dto,"items":items,
        "items_real":[i for i in items if i["xyz"]!="N/A"],
        "items_few_data":[i for i in items if i["xyz"]=="N/A"],
        "items_expenses":[i for i in items if i["revenue"]<=0],"matrix":matrix,
        "total_profit":total_profit,"positive_profit_base":math.fsum(max(i["profit"],0) for i in items),
        "total_revenue":preview["income"],"capital_available":cap_available,
        "min_active":settings["min_active_months"],"settings":settings,
        "model_version":MODEL_VERSION,"basis":BASIS,"cogs_estimated":preview["cogs_estimated"],
        "xyz_basis":"delivered units; complete calendar months; zeros included; completeness not independently verified",
        "capital_basis":"latest available stock snapshot; historical cost at stock date"}


def _compute(dfrom, dto, settings, db_path=None):
    if db_path is None:
        from .config import DB_PATH
        db_path = DB_PATH
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ValueError("Database not found")
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        return compute_from_connection(conn,dfrom.isoformat(),dto.isoformat(),settings)


def _build_full_rows(data):
    return [[i["sku"],i["abc"],i["xyz"],i["matrix"],round(i["revenue"],2),round(i["profit"],2),
        i["qty"],i["share"],i["cum"],i["active_months"],i["cv"] if i["cv"] is not None else "",
        round(i["capital"],2),i["recommendation"]] for i in data["items"]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    today = date.today()
    parser.add_argument("--from",dest="dfrom",default=(today-timedelta(days=270)).isoformat())
    parser.add_argument("--to",dest="dto",default=(today-timedelta(days=1)).isoformat())
    parser.add_argument("--db")
    parser.add_argument("--out-dir",default=str(OUT_DIR))
    parser.add_argument("--local",action="store_true",help="Preview only (default)")
    parser.add_argument("--publish",action="store_true",help="Blocked until preview and audit approval")
    args = parser.parse_args(argv)
    if args.publish:
        parser.error("Publishing is blocked: existing ABC snapshots and Sheets must remain unchanged")
    try:
        data = _compute(date.fromisoformat(args.dfrom),date.fromisoformat(args.dto),DEFAULT_SETTINGS,args.db)
        folder = Path(args.out_dir);folder.mkdir(parents=True,exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        prefix = f"abc_xyz_preview_{args.dfrom}_{args.dto}_{stamp}"
        with (folder/(prefix+".csv")).open("x",encoding="utf-8-sig",newline="") as f:
            writer = csv.writer(f,delimiter=";");writer.writerow(HEADER_FULL);writer.writerows(_build_full_rows(data))
        summary = {k:data[k] for k in ("period","model_version","basis","xyz_basis","capital_basis",
            "total_profit","positive_profit_base","total_revenue","cogs_estimated")}
        summary.update(sku_count=len(data["items"]),loss_sku_count=sum(i["profit"]<0 for i in data["items"]),
                       preview_only=True,settings_source="defaults; Google Sheets not read")
        with (folder/(prefix+".json")).open("x",encoding="utf-8") as f:
            json.dump(summary,f,ensure_ascii=False,allow_nan=False,indent=2)
    except (ValueError,KeyError,OverflowError,sqlite3.Error,OSError) as exc:
        parser.exit(1,f"ABC preview failed: {exc}\n")
    print(json.dumps(summary,ensure_ascii=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
