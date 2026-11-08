"""unitka/analytics_db.py — БД-хелперы аналитического блока.

Не заменяет unitka/db.py: финансовый пайплайн (calc_margin, calc_money_in_goods,
run_unit) продолжает работать как раньше.

Создаёт две таблицы:
  * analytics_daily — воронка по SKU (Блок 1, отложен; таблица создаётся заранее)
  * abc_xyz         — ABC/XYZ ассортимента (Блок 4)
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path(os.getenv("OZON_DB", str(PROJECT_ROOT / "app" / "ozon.db")))

DDL = """
-- Воронка по SKU (Блок 1 — заполнится позже, из Excel-выгрузки)
CREATE TABLE IF NOT EXISTS analytics_daily (
    date                 TEXT    NOT NULL,
    sku                  INTEGER NOT NULL,
    views_search         INTEGER,
    views_pdp            INTEGER,
    to_cart              INTEGER,
    session_view_search  INTEGER,
    ordered_units        INTEGER,
    revenue              REAL,
    conv_view_to_order   REAL,
    conv_cart_to_order   REAL,
    position_avg         REAL,
    position_category    REAL,
    raw_json             TEXT,
    fetched_at           TEXT,
    PRIMARY KEY (date, sku)
);
CREATE INDEX IF NOT EXISTS idx_analytics_daily_sku  ON analytics_daily(sku, date);
CREATE INDEX IF NOT EXISTS idx_analytics_daily_date ON analytics_daily(date);

-- ABC/XYZ ассортимента (Блок 4)
CREATE TABLE IF NOT EXISTS abc_xyz (
    period       TEXT    NOT NULL,
    sku          INTEGER NOT NULL,
    profit       REAL,
    revenue      REAL,
    qty          INTEGER,
    abc_class    TEXT,
    xyz_class    TEXT,
    matrix       TEXT,
    share_profit REAL,
    cum_share    REAL,
    cv           REAL,
    capital      REAL,
    recommendation TEXT,
    fetched_at   TEXT,
    PRIMARY KEY (period, sku)
);
CREATE INDEX IF NOT EXISTS idx_abc_xyz_period ON abc_xyz(period);
CREATE INDEX IF NOT EXISTS idx_abc_xyz_matrix ON abc_xyz(period, matrix);
"""


def connect() -> sqlite3.Connection:
    """Сначала пробуем общий connect() из unitka.db, иначе — своё подключение."""
    try:
        from unitka.db import connect as _shared_connect  # type: ignore
        conn = _shared_connect()
        if conn is not None:
            return conn
    except Exception as exc:  # noqa: BLE001
        log.debug("unitka.db.connect() недоступен: %s", exc)

    conn = sqlite3.connect(str(DEFAULT_DB), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Создаёт аналитические таблицы, если их ещё нет. Идемпотентно."""
    conn.executescript(DDL)
    conn.commit()


def _main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    conn = connect()
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    log.info("Подключение: %s", db_path)
    ensure_schema(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('analytics_daily','abc_xyz') ORDER BY name"
    ).fetchall()
    names = [r[0] for r in rows]
    log.info("Таблицы аналитики в БД: %s", names)

    for name in ("analytics_daily", "abc_xyz"):
        cnt = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        log.info("  %-18s строк: %s", name, cnt)

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())