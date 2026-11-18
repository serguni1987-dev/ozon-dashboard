"""Разово: справочник типов начислений в accrual_types."""
from datetime import datetime

from . import config, db
from .ozon_client import OzonClient


def main():
    from .ingestion_safety import atomic,objects,integer,identifier
    config.check_credentials();rows=[(integer(t.get('id'),minimum=1),identifier(t.get('name')),t.get('description'),datetime.now().isoformat(timespec='seconds')) for t in objects(OzonClient().accrual_types())]
    if not rows:raise ValueError('Empty accrual types; previous catalogue preserved')
    con=db.connect()
    try:
        with atomic(con):con.executemany('INSERT OR REPLACE INTO accrual_types(id,name,description,fetched_at) VALUES (?,?,?,?)',rows)
    finally:con.close()
    return len(rows)


if __name__ == "__main__":
    main()
