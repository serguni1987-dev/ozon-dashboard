"""Restricted SQLite reads for AI. Does not authorize financial interpretations."""
from contextlib import closing
from pathlib import Path
import math
import re
import sqlite3
import time

COLUMNS = {
    "monthly_reports": frozenset({
        "month", "year", "month_num", "report_number", "report_date",
        "period_start", "period_end", "sale_price_sum", "bonus_sum",
        "coinvestment_sum", "gross_commission_sum", "fetched_at",
    }),
    "abc_xyz": frozenset({"period", "sku", "fetched_at"}),
}
FUNCTIONS = frozenset({
    "sum", "count", "avg", "min", "max", "round", "abs", "coalesce",
    "ifnull", "nullif", "date", "datetime", "strftime", "substr",
    "substring", "lower", "upper", "trim", "replace", "length",
})


def open_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)


def authorize(action, arg1, arg2, database, origin):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        allowed = COLUMNS.get((arg1 or "").lower())
        if allowed is not None and (database == "main" or (database is None and not arg2)):
            if not arg2 or arg2.lower() in allowed:
                return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if (arg2 or arg1 or "").lower() in FUNCTIONS:
            return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def get_schema(path):
    lines = []
    with closing(open_readonly(path)) as con:
        con.execute("PRAGMA query_only=ON")
        for table, allowed in sorted(COLUMNS.items()):
            cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
            shown = [f"{r[1]} {r[2]}" for r in cols if r[1].lower() in allowed]
            if shown:
                lines.append(table + " (" + ", ".join(shown) + ")")
    return "\n".join(lines)


def read_query(path, sql, max_rows=100, seconds=2.0):
    if type(max_rows) is not int or not 1 <= max_rows <= 100:
        raise ValueError("max_rows must be between 1 and 100")
    if isinstance(seconds, bool) or not math.isfinite(seconds) or not 0 < seconds <= 5:
        raise ValueError("seconds must be positive and at most 5")
    if not isinstance(sql, str) or len(sql) > 10000:
        raise ValueError("Invalid SQL size")
    if not re.match(r"^(SELECT|WITH)\b", sql.strip(), re.I):
        raise ValueError("Only SELECT or WITH ... SELECT is allowed")
    with closing(open_readonly(path)) as con:
        con.execute("PRAGMA query_only=ON")
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
        con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 10000)
        con.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 64)
        con.set_authorizer(authorize)
        deadline = time.monotonic() + seconds
        steps = 0
        def interrupted():
            nonlocal steps
            steps += 1000
            return int(steps >= 1000000 or time.monotonic() >= deadline)
        con.set_progress_handler(interrupted, 1000)
        cursor = con.execute(sql)
        if cursor.description is None:
            raise ValueError("A result set is required")
        names = [c[0] for c in cursor.description]
        if len(set(names)) != len(names):
            raise ValueError("Use unique column aliases")
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise ValueError("Too many rows; aggregate or use LIMIT")
        for row in rows:
            if any(isinstance(v, bytes) or (isinstance(v, str) and len(v) > 8000) for v in row):
                raise ValueError("Result cell exceeds safe output limits")
        return [dict(zip(names, row)) for row in rows]
