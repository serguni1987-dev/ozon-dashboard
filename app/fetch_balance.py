"""
fetch_balance.py — тянет точный баланс из /v1/finance/balance.
Сохраняет в таблицу balance_history.
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
URL = "https://api-seller.ozon.ru/v1/finance/balance"
DB = "ozon.db"


def init_table(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS balance_history (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        fetched_at        TEXT NOT NULL,
        date_from         TEXT NOT NULL,
        date_to           TEXT NOT NULL,
        opening_balance   REAL,
        closing_balance   REAL,
        accrued           REAL,
        payments          REAL,
        sales_amount      REAL,
        sales_fee         REAL,
        sales_revenue     REAL,
        sales_points      REAL,
        returns_amount    REAL,
        returns_revenue   REAL,
        returns_points    REAL,
        raw_json          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_bh_fetched ON balance_history(fetched_at);
    """)
    con.commit()


def to_float(d):
    if not d:
        return 0.0
    if isinstance(d, (int, float)):
        return float(d)
    try:
        return float(d.get("value") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def to_float_str(v):
    """points_for_discounts приходит строкой."""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main():
    print("=" * 80)
    print("ЗАГРУЗКА БАЛАНСА ИЗ OZON API")
    print("=" * 80)

    # Период — 30 дней
    date_to = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    print(f"\n[1] Период: {date_from} — {date_to}")

    body = {"date_from": date_from, "date_to": date_to}
    r = requests.post(URL, headers=H, json=body, timeout=60)

    if r.status_code != 200:
        print(f"  [{r.status_code}] {r.text[:500]}")
        return

    data = r.json()
    total = data.get("total") or {}
    cf = data.get("cashflows") or {}

    # Извлекаем ключевые цифры
    opening_balance = to_float(total.get("opening_balance"))
    closing_balance = to_float(total.get("closing_balance"))
    accrued = to_float(total.get("accrued"))
    payments_list = total.get("payments") or []
    payments = sum(to_float(p) for p in payments_list)

    sales = cf.get("sales") or {}
    sales_amount = to_float(sales.get("amount"))
    sales_fee = to_float(sales.get("fee"))
    sales_details = sales.get("amount_details") or {}
    sales_revenue = to_float(sales_details.get("revenue"))
    sales_points = to_float_str(sales_details.get("points_for_discounts"))

    returns = cf.get("returns") or {}
    returns_amount = to_float(returns.get("amount"))
    returns_details = returns.get("amount_details") or {}
    returns_revenue = to_float(returns_details.get("revenue"))
    returns_points = to_float_str(returns_details.get("points_for_discounts"))

    # Сохраняем
    con = sqlite3.connect(DB)
    init_table(con)
    con.execute("""
        INSERT INTO balance_history
        (fetched_at, date_from, date_to,
         opening_balance, closing_balance, accrued, payments,
         sales_amount, sales_fee, sales_revenue, sales_points,
         returns_amount, returns_revenue, returns_points, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        date_from, date_to,
        opening_balance, closing_balance, accrued, payments,
        sales_amount, sales_fee, sales_revenue, sales_points,
        returns_amount, returns_revenue, returns_points,
        json.dumps(data, ensure_ascii=False),
    ))
    con.commit()

    # Показываем
    print(f"\n[2] БАЛАНС НА СЧЕТУ У OZON")
    print(f"  На начало периода:  {opening_balance:>12,.2f} ₽")
    print(f"  Начислено:          {accrued:>12,.2f} ₽")
    print(f"  Выплачено:          {payments:>12,.2f} ₽")
    print(f"  ─────────────────────────────────")
    print(f"  БАЛАНС СЕЙЧАС:      {closing_balance:>12,.2f} ₽")

    print(f"\n[3] ДВИЖЕНИЕ ЗА 30 ДНЕЙ")
    print(f"  Продажи:            {sales_amount:>12,.2f} ₽")
    print(f"    в т.ч. выручка:   {sales_revenue:>12,.2f} ₽")
    print(f"    в т.ч. баллы:     {sales_points:>12,.2f} ₽")
    print(f"    удержано:         {sales_fee:>12,.2f} ₽")
    print(f"  Возвраты:           {returns_amount:>12,.2f} ₽")
    print(f"    в т.ч. выручка:   {returns_revenue:>12,.2f} ₽")
    print(f"    в т.ч. баллы:     {returns_points:>12,.2f} ₽")

    # Услуги
    services = cf.get("services") or []
    if services:
        print(f"\n  Услуги Ozon:")
        total_serv = 0
        for s in services:
            name = s.get("name", "?")
            amt = to_float(s.get("amount"))
            total_serv += amt
            if abs(amt) > 100:
                print(f"    {name:<40} {amt:>10,.2f} ₽")
        print(f"    {'ИТОГО услуги':<40} {total_serv:>10,.2f} ₽")

    # Статистика
    n = con.execute("SELECT COUNT(*) FROM balance_history").fetchone()[0]
    print(f"\n[4] В balance_history: {n} записей")
    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
