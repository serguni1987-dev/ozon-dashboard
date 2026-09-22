"""
fetch_current_stocks.py — тянет актуальные остатки из Ozon API.
Сохраняет в таблицу current_stocks в SQLite.
"""
import os
import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v4/product/info/stocks"
DB = "ozon.db"


def init_table(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS current_stocks (
        offer_id      TEXT PRIMARY KEY,
        sku           INTEGER,
        fbo_present   INTEGER,
        fbo_reserved  INTEGER,
        fbs_present   INTEGER,
        fbs_reserved  INTEGER,
        total_present INTEGER,
        total_reserved INTEGER,
        fetched_at    TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cs_sku ON current_stocks(sku);
    """)
    con.commit()


def fetch_page(last_id=""):
    body = {
        "filter": {"visibility": "ALL"},
        "cursor": last_id,
        "limit": 1000,
    }
    r = requests.post(URL, headers=H, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[{r.status_code}] {r.text[:500]}")
        return [], ""
    data = r.json()
    items = data.get("items") or []
    last_id_new = data.get("cursor") or ""
    return items, last_id_new


def main():
    print("=" * 90)
    print("ЗАГРУЗКА ОСТАТКОВ ИЗ OZON API")
    print("=" * 90)

    con = sqlite3.connect(DB)
    init_table(con)
    cur = con.cursor()

    # Очистка перед перезагрузкой
    cur.execute("DELETE FROM current_stocks")

    last_id = ""
    page = 1
    total = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    while True:
        items, cursor = fetch_page(last_id)
        if not items:
            break
        print(f"  страница {page}: {len(items)} SKU")

        for it in items:
            oid = it.get("offer_id")
            sku = it.get("product_id") or it.get("sku")
            if not oid:
                continue

            stocks = it.get("stocks") or []
            fbo_present = fbo_reserved = fbs_present = fbs_reserved = 0

            for s in stocks:
                typ = s.get("type", "").lower()
                present = s.get("present", 0) or 0
                reserved = s.get("reserved", 0) or 0
                if typ == "fbo":
                    fbo_present = present
                    fbo_reserved = reserved
                elif typ == "fbs":
                    fbs_present = present
                    fbs_reserved = reserved

            cur.execute("""
                INSERT OR REPLACE INTO current_stocks
                (offer_id, sku, fbo_present, fbo_reserved,
                 fbs_present, fbs_reserved, total_present, total_reserved, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                oid, sku, fbo_present, fbo_reserved,
                fbs_present, fbs_reserved,
                fbo_present + fbs_present, fbo_reserved + fbs_reserved,
                now,
            ))
            total += 1

        last_id = cursor
        if not last_id:
            break
        page += 1
        if page > 20:
            break

    con.commit()

    # Статистика
    n_total = cur.execute("SELECT COUNT(*) FROM current_stocks").fetchone()[0]
    n_positive = cur.execute("SELECT COUNT(*) FROM current_stocks WHERE total_present > 0").fetchone()[0]
    n_zero = cur.execute("SELECT COUNT(*) FROM current_stocks WHERE total_present = 0").fetchone()[0]

    total_value = cur.execute("""
        SELECT SUM(cs.total_present * p.cost_price)
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        WHERE p.cost_price > 0
    """).fetchone()[0] or 0

    print(f"\n  Обновлено:                {total}")
    print(f"  Всего в current_stocks:   {n_total}")
    print(f"  С остатком > 0:           {n_positive}")
    print(f"  С остатком = 0:           {n_zero}")
    print(f"\n  💰 Заморожено в складе:   {total_value:>14,.0f} ₽")

    con.close()
    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()
