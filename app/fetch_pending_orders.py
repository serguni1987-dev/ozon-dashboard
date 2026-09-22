"""
fetch_pending_orders.py - считает заказы в доставке (FBS + FBO).
Сохраняет в таблицу pending_orders.
"""
import os
import json
import requests
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
DB = "ozon.db"

# Статусы, которые считаем "в доставке"
PENDING_STATUSES = ["delivering", "sent_by_seller"]


def init_table(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS pending_orders (
        posting_number TEXT PRIMARY KEY,
        scheme         TEXT,
        status         TEXT,
        created_at     TEXT,
        in_process_at  TEXT,
        total_price    REAL,
        quantity       INTEGER,
        fetched_at     TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_orders(status);
    CREATE INDEX IF NOT EXISTS idx_pending_scheme ON pending_orders(scheme);
    """)
    con.commit()


def fetch_postings(url, since, to, scheme):
    """Тянет заказы одной схемы (FBS или FBO)."""
    all_postings = []
    offset = 0
    limit = 100  # максимум для FBO

    while True:
        body = {
            "dir": "DESC",
            "filter": {
                "since": since,
                "to": to,
                "status": "delivering",
            },
            "limit": limit,
            "offset": offset,
            "with": {"analytics_data": False, "financial_data": False},
        }
        r = requests.post(url, headers=H, json=body, timeout=60)
        if r.status_code != 200:
            print(f"  [{r.status_code}] {scheme}: {r.text[:300]}")
            return all_postings
        data = r.json()
        result = data.get("result") or {}
        postings = result.get("postings") or []
        if not postings:
            break
        all_postings.extend(postings)
        if not result.get("has_next"):
            break
        offset += limit
        if offset > 10000:
            break
    return all_postings


def extract_price(posting):
    """Сумма заказа — из products[].price × quantity."""
    total = 0.0
    qty = 0
    for p in posting.get("products") or []:
        try:
            price = float(p.get("price") or 0)
        except (TypeError, ValueError):
            price = 0
        quantity = p.get("quantity") or 1
        total += price * quantity
        qty += quantity
    return total, qty


def main():
    print("=" * 80)
    print("ЗАКАЗЫ В ДОСТАВКЕ (delivering)")
    print("=" * 80)

    # Период — 60 дней назад
    to_dt = datetime.now()
    since_dt = to_dt - timedelta(days=60)
    since = since_dt.strftime("%Y-%m-%dT00:00:00Z")
    to = to_dt.strftime("%Y-%m-%dT23:59:59Z")

    print(f"\n[1] Период: {since[:10]} - {to[:10]}")

    con = sqlite3.connect(DB)
    init_table(con)

    # Очищаем перед перезагрузкой
    con.execute("DELETE FROM pending_orders WHERE status IN ('delivering', 'sent_by_seller')")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_amount = 0.0
    total_qty = 0
    total_count = 0

    for scheme, url in [
        ("FBS", "https://api-seller.ozon.ru/v3/posting/fbs/list"),
        ("FBO", "https://api-seller.ozon.ru/v3/posting/fbo/list"),
    ]:
        print(f"\n[2] Схема {scheme}...")
        postings = fetch_postings(url, since, to, scheme)
        print(f"  Найдено: {len(postings)} заказов")

        for p in postings:
            posting_number = p.get("posting_number") or ""
            status = p.get("status") or ""
            if status not in PENDING_STATUSES:
                continue
            price, qty = extract_price(p)
            con.execute("""
                INSERT OR REPLACE INTO pending_orders
                (posting_number, scheme, status, created_at, in_process_at,
                 total_price, quantity, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                posting_number, scheme, status,
                p.get("created_at") or "",
                p.get("in_process_at") or "",
                price, qty, now_str,
            ))
            total_amount += price
            total_qty += qty
            total_count += 1

    con.commit()

    # Статистика
    print(f"\n[3] ИТОГИ:")
    print(f"  Заказов в доставке:  {total_count}")
    print(f"  Позиций всего:       {total_qty}")
    print(f"  Сумма (₽):           {total_amount:>12,.2f}")

    # По схемам
    print(f"\n[4] По схемам:")
    for scheme, count, amount in con.execute("""
        SELECT scheme, COUNT(*), SUM(total_price)
        FROM pending_orders
        WHERE status IN ('delivering', 'sent_by_seller')
        GROUP BY scheme
    """):
        print(f"  {scheme:<5} {count:>3} заказов = {amount:>12,.2f} ₽")

    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
