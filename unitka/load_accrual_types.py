"""Разово: справочник типов начислений в accrual_types."""
from datetime import datetime

from . import config, db
from .ozon_client import OzonClient


def main():
    config.check_credentials()
    client = OzonClient()
    types = client.accrual_types()
    now = datetime.now().isoformat(timespec="seconds")
    con = db.connect()
    db.init_schema(con)
    for t in types:
        con.execute("""INSERT OR REPLACE INTO accrual_types
                       (id, name, description, fetched_at) VALUES (?, ?, ?, ?)""",
                    (int(t.get("id") or 0), t.get("name"), t.get("description"), now))
    con.commit()
    con.close()
    print(f"Загружено {len(types)} типов начислений")
    for t in sorted(types, key=lambda x: x.get("id", 0)):
        print(f"  {t.get('id'):>5}  {t.get('name')}")


if __name__ == "__main__":
    main()
