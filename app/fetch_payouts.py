"""
fetch_payouts.py — тянет недельные выплаты из cash-flow-statement/list.
Сохраняет в таблицу payouts.
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
URL = "https://api-seller.ozon.ru/v1/finance/cash-flow-statement/list"
DB = "ozon.db"


def init_table(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS payouts (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        period_begin      TEXT NOT NULL,
        period_end        TEXT NOT NULL,
        orders_amount     REAL,
        returns_amount    REAL,
        commission_amount REAL,
        services_amount   REAL,
        delivery_amount   REAL,
        total_amount      REAL,
        status            TEXT DEFAULT 'expected',
        fetched_at        TEXT
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_po_period ON payouts(period_begin, period_end);
    """)
    con.commit()


def main():
    print("=" * 80)
    print("ЗАГРУЗКА ВЫПЛАТ ИЗ OZON API")
    print("=" * 80)

    # Период — 60 дней назад (чтобы охватить больше недель)
    date_to = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
    date_from = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%dT00:00:00Z")

    print(f"\n[1] Период: {date_from} — {date_to}")

    body = {"date": {"from": date_from, "to": date_to}, "page": 1, "page_size": 100}
    r = requests.post(URL, headers=H, json=body, timeout=60)

    if r.status_code != 200:
        print(f"  [{r.status_code}] {r.text[:500]}")
        return

    data = r.json()
    result = data.get("result") or {}
    flows = result.get("cash_flows") or []
    print(f"  Получено недель: {len(flows)}")

    con = sqlite3.connect(DB)
    init_table(con)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    print(f"\n[2] ОБРАБОТКА:")
    print(f"  {'Период':<26} {'Заказы':>10} {'Комиссия':>10} {'Услуги':>10} {'Логист':>10} {'ИТОГО':>12}")
    print("  " + "-" * 88)

    for flow in flows:
        period = flow.get("period") or {}
        begin = (period.get("begin") or "")[:10]
        end = (period.get("end") or "")[:10]
        if not begin:
            continue

        orders = flow.get("orders_amount") or 0
        returns = flow.get("returns_amount") or 0
        comm = flow.get("commission_amount") or 0
        serv = flow.get("services_amount") or 0
        deliv = flow.get("item_delivery_and_return_amount") or 0

        total = orders + returns + comm + serv + deliv

        # Определяем статус: если неделя уже закончилась и мы её видели в выплатах — received, иначе expected
        # Упрощённо: если end < сегодня-7д — received, иначе expected
        end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now()
        days_ago = (datetime.now() - end_dt).days
        status = "received" if days_ago > 7 else "expected"

        con.execute("""
            INSERT OR REPLACE INTO payouts
            (period_begin, period_end, orders_amount, returns_amount,
             commission_amount, services_amount, delivery_amount,
             total_amount, status, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (begin, end, orders, returns, comm, serv, deliv, total, status, now))
        inserted += 1

        print(f"  {begin} - {end:<12} {orders:>10,.0f} {comm:>10,.0f} "
              f"{serv:>10,.0f} {deliv:>10,.0f} {total:>12,.0f}")

    con.commit()

    # Статистика
    n_total = con.execute("SELECT COUNT(*) FROM payouts").fetchone()[0]
    n_expected = con.execute("SELECT COUNT(*) FROM payouts WHERE status='expected'").fetchone()[0]
    sum_expected = con.execute("SELECT SUM(total_amount) FROM payouts WHERE status='expected'").fetchone()[0] or 0

    print(f"\n[3] ИТОГИ:")
    print(f"  Всего недель в БД:      {n_total}")
    print(f"  Ожидаемых к выплате:    {n_expected}")
    print(f"  Сумма к выплате:        {sum_expected:>12,.0f} ₽")

    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
