"""Offline data checks and consistent SQLite backup. No API calls or migrations."""
from __future__ import annotations
import argparse
import csv
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

TABLES = ("postings_daily", "realization_daily", "monthly_reports", "abc_xyz",
          "accruals", "accruals_services", "monthly_realization_rows",
          "products", "product_cost_history", "stock_daily", "current_prices")


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def inspect_database(path, query_seconds=10):
    if query_seconds <= 0:
        raise ValueError("query_seconds must be positive")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "database": Path(path).name, "checks": [], "tables": {}}
    def add(name, status, details):
        report["checks"].append({"check": name, "status": status, "details": details})
    with closing(readonly(path)) as con:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        def query(sql, params=()):
            deadline = time.monotonic() + query_seconds
            con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            try:
                return con.execute(sql, params).fetchall()
            finally:
                con.set_progress_handler(None, 0)
        def check(name, sql, params=(), positive_is_issue=True):
            try:
                rows = query(sql, params)
                value = rows[0][0] if rows else None
                status = "WARN" if positive_is_issue and value else "INFO"
                add(name, status, rows)
            except sqlite3.Error as exc:
                add(name, "ERROR", str(exc))
        try:
            result = query("PRAGMA quick_check")
            add("sqlite_quick_check", "OK" if result == [("ok",)] else "ERROR", result)
            existing = {r[0] for r in query("SELECT name FROM sqlite_schema WHERE type='table'")}
            for table in TABLES:
                if table not in existing:
                    add("table:" + table, "WARN", "Missing: availability requirements need review")
                    continue
                cols = {r[1] for r in query(f'PRAGMA table_info("{table}")')}
                info = {"columns": sorted(cols)}
                report["tables"][table] = info
                try:
                    info["rows"] = query(f'SELECT COUNT(*) FROM "{table}"')[0][0]
                    for field in ("date", "fetched_at"):
                        if field in cols:
                            info[field + "_range"] = query(
                                f'SELECT MIN("{field}"), MAX("{field}") FROM "{table}"')[0]
                except sqlite3.Error as exc:
                    add("inventory:" + table, "ERROR", str(exc))
            def has(table, *cols):
                return set(cols) <= set(report["tables"].get(table, {}).get("columns", []))
            if has("abc_xyz", "period", "sku", "profit", "fetched_at"):
                try:
                    periods = query("SELECT period,COUNT(*),COUNT(DISTINCT sku),MIN(profit),MAX(profit),MAX(fetched_at) FROM abc_xyz GROUP BY period ORDER BY period DESC")
                    report["abc_periods"] = periods
                    add("abc_period_selection", "WARN" if len(periods)>1 else "INFO",
                        "Select one calculation snapshot; do not sum overlapping periods")
                except sqlite3.Error as exc:
                    add("abc_periods", "ERROR", str(exc))
                check("abc_duplicate_period_sku", "SELECT COUNT(*) FROM (SELECT period,sku FROM abc_xyz GROUP BY period,sku HAVING COUNT(*)>1)")
                check("abc_missing_profit", "SELECT COUNT(*) FROM abc_xyz WHERE profit IS NULL")
            if has("product_cost_history", "sku", "date_from", "cost_price"):
                check("cost_missing_or_nonpositive", "SELECT COUNT(*) FROM product_cost_history WHERE cost_price IS NULL OR cost_price<=0")
                check("cost_duplicate_effective_date", "SELECT COUNT(*) FROM (SELECT sku,date_from FROM product_cost_history GROUP BY sku,date_from HAVING COUNT(*)>1)")
                if has("postings_daily", "sku", "date"):
                    check("postings_without_positive_historical_cost", """SELECT COUNT(*) FROM postings_daily p
                        WHERE COALESCE((SELECT h.cost_price FROM product_cost_history h
                        WHERE h.sku=p.sku AND h.date_from<=p.date
                        ORDER BY h.date_from DESC LIMIT 1),0)<=0""")
            if has("monthly_reports", "year", "report_number"):
                check("monthly_repeated_report_keys", "SELECT COUNT(*) FROM (SELECT year,report_number FROM monthly_reports WHERE report_number IS NOT NULL AND report_number<>'' GROUP BY year,report_number HAVING COUNT(*)>1)")
                add("monthly_key_review", "INFO", "Repeated keys are candidates for review, not permission to delete rows")
            for table in ("postings_daily", "realization_daily", "accruals", "accruals_services"):
                if has(table, "date"):
                    check("invalid_date:"+table, f'SELECT COUNT(*) FROM "{table}" WHERE date IS NULL OR date(date) IS NULL')
            if has("realization_daily", "sale_price", "sale_amount", "quantity", "bonus", "coinvestment"):
                add("realization_semantics", "WARN", "Unit versus row amounts, return signs and support accounting are NOT verified")
            add("financial_reconciliation", "WARN", "Not performed: requires approved definitions and source reports")
        except sqlite3.Error as exc:
            add("audit_failed", "ERROR", str(exc))
        finally:
            con.rollback()
    report["summary"] = {s: sum(c["status"] == s for c in report["checks"])
                         for s in ("OK", "INFO", "WARN", "ERROR")}
    report["can_reprice"] = False
    report["can_reprice_reason"] = "This diagnostic never authorizes price writes"
    return report


def backup_database(source, target, max_seconds=120):
    source, target = Path(source).resolve(), Path(target).resolve()
    if max_seconds <= 0 or source == target:
        raise ValueError("Invalid backup target or deadline")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb"):
        pass
    try:
        deadline = time.monotonic() + max_seconds
        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise TimeoutError("Backup deadline exceeded")
        with closing(readonly(source)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst, pages=256, progress=progress, sleep=0.05)
            dst.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
            if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("Backup integrity check failed")
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out/data_quality"))
    parser.add_argument("--backup", type=Path, help="Create new backup before inspection; never overwrite")
    args = parser.parse_args(argv)
    if args.db is None:
        from .config import DB_PATH
        args.db = Path(DB_PATH)
    destinations = [args.out / "report.json", args.out / "checks.csv"]
    if any(p.resolve() == args.db.resolve() for p in destinations):
        parser.error("Report destination cannot be the source database")
    if args.backup and any(args.backup.resolve()==p.resolve() for p in destinations):
        parser.error("Backup cannot be overwritten by a report")
    try:
        if args.backup:
            backup_database(args.db, args.backup)
        report = inspect_database(args.db)
        args.out.mkdir(parents=True, exist_ok=True)
        destinations[0].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        with destinations[1].open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["check", "status", "details"])
            writer.writeheader()
            for item in report["checks"]:
                writer.writerow({**item, "details": json.dumps(item["details"], ensure_ascii=False)})
        print(json.dumps(report["summary"], ensure_ascii=False))
        print("Report files:", args.out)
        return 2 if report["summary"]["ERROR"] else (1 if report["summary"]["WARN"] else 0)
    except (OSError, sqlite3.Error, ValueError, RuntimeError, TimeoutError) as exc:
        print(f"Diagnostic failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
