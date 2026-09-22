"""
fetch_current_prices.py — тянет текущие цены из Ozon API (/v5/product/info/prices).
Сохраняет в таблицу current_prices с полной структурой (включая price_indexes).
"""
import os
import requests
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v5/product/info/prices"
DB = "ozon.db"


def init_table(con):
    """Пересоздаём с расширенной структурой."""
    con.executescript("""
    DROP TABLE IF EXISTS current_prices;
    CREATE TABLE current_prices (
        offer_id           TEXT PRIMARY KEY,
        sku                INTEGER,
        price              REAL,
        old_price          REAL,
        min_price          REAL,
        marketing_price    REAL,
        net_price          REAL,
        currency           TEXT,
        acquiring          REAL,
        sales_percent_fbo  REAL,
        sales_percent_fbs  REAL,
        price_index_color  TEXT,
        price_index_value  REAL,
        price_index_min    REAL,
        volume_weight      REAL,
        fetched_at         TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cp_sku ON current_prices(sku);
    CREATE INDEX IF NOT EXISTS idx_cp_color ON current_prices(price_index_color);
    """)
    con.commit()


def fetch_page(last_id=""):
    body = {"filter": {"visibility": "ALL"}, "cursor": last_id, "limit": 1000}
    r = requests.post(URL, headers=H, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[{r.status_code}] {r.text[:500]}")
        return [], ""
    data = r.json()
    return data.get("items") or [], data.get("cursor") or ""


def tf(v):
    """to_float — безопасно."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


def main():
    print("=" * 90)
    print("ЗАГРУЗКА ТЕКУЩИХ ЦЕН ИЗ OZON API")
    print("=" * 90)

    con = sqlite3.connect(DB)
    init_table(con)
    cur = con.cursor()

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
            sku = it.get("product_id")
            if not oid:
                continue

            # Цены — внутри it["price"]
            p = it.get("price") or {}
            price         = tf(p.get("price"))
            old_price     = tf(p.get("old_price"))
            min_price     = tf(p.get("min_price"))
            marketing_p   = tf(p.get("marketing_seller_price"))
            net_price     = tf(p.get("net_price"))
            currency      = p.get("currency_code") or "RUB"

            # Эквайринг
            acquiring = tf(it.get("acquiring"))

            # Гросс-комиссия
            comm = it.get("commissions") or {}
            sales_fbo = tf(comm.get("sales_percent_fbo"))
            sales_fbs = tf(comm.get("sales_percent_fbs"))

            # Индекс цены
            idx = it.get("price_indexes") or {}
            color = idx.get("color_index") or ""
            ozon_idx = idx.get("ozon_index_data") or {}
            idx_value = tf(ozon_idx.get("price_index_value"))
            idx_min = tf(ozon_idx.get("min_price"))

            # Объёмный вес
            volume_weight = tf(it.get("volume_weight"))

            cur.execute("""
                INSERT OR REPLACE INTO current_prices
                (offer_id, sku, price, old_price, min_price, marketing_price,
                 net_price, currency, acquiring, sales_percent_fbo, sales_percent_fbs,
                 price_index_color, price_index_value, price_index_min,
                 volume_weight, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                oid, sku, price, old_price, min_price, marketing_p,
                net_price, currency, acquiring, sales_fbo, sales_fbs,
                color, idx_value, idx_min,
                volume_weight, now,
            ))
            total += 1

        last_id = cursor
        if not last_id:
            break
        page += 1
        if page > 20:
            print("  стоп: >20 страниц")
            break

    con.commit()

    # Статистика
    n_total = cur.execute("SELECT COUNT(*) FROM current_prices").fetchone()[0]
    n_with_price = cur.execute("SELECT COUNT(*) FROM current_prices WHERE price > 0").fetchone()[0]
    n_with_idx = cur.execute("SELECT COUNT(*) FROM current_prices WHERE price_index_color != ''").fetchone()[0]

    print(f"\n  Обновлено:                {total}")
    print(f"  Всего в current_prices:   {n_total}")
    print(f"  С ценой:                  {n_with_price}")
    print(f"  С индексом цены:          {n_with_idx}")

    # Распределение по индексу
    print(f"\n  Индекс цены (color):")
    for r in cur.execute("""
        SELECT price_index_color, COUNT(*)
        FROM current_prices
        WHERE price_index_color != ''
        GROUP BY price_index_color
        ORDER BY COUNT(*) DESC
    """):
        print(f"    {r[0]:<10} {r[1]:>5} SKU")

    # Наши изменённые SKU
    print(f"\n  Наши SKU после apply_prices:")
    print(f"  {'Offer ID':<18} {'Цена':>8} {'Old':>8} {'Min':>8} {'Индекс':<8}")
    print("  " + "-" * 60)
    for oid in ["OCE013E4", "OCPR0022418030", "OCER002E418030",
                "OCER005E418030", "OCER013E416030", "OCER013E418030"]:
        r = cur.execute("""
            SELECT offer_id, price, old_price, min_price, price_index_color
            FROM current_prices WHERE offer_id = ?
        """, (oid,)).fetchone()
        if r:
            p = f"{r[1]:,.0f}" if r[1] else "—"
            o = f"{r[2]:,.0f}" if r[2] else "—"
            m = f"{r[3]:,.0f}" if r[3] else "—"
            print(f"  {r[0]:<18} {p:>8} {o:>8} {m:>8} {r[4]:<8}")

    con.close()
    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()
