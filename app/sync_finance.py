"""
sync_finance.py — синхронизация финансовых начислений из Ozon API.
Тянет /v1/finance/accrual/by-day с последней даты в БД (или с 2026-09-01).
Идемпотентно: повторный запуск не создаёт дублей.
"""
import os
import json
import sys
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
BASE = "https://api-seller.ozon.ru"
DB = "ozon.db"

START_DEFAULT = "2026-09-01"
END = datetime.now().strftime("%Y-%m-%d")

# Переопределяется через --from и --to
def parse_args():
    args = {"date_from": None, "date_to": None}
    for arg in sys.argv[1:]:
        if arg.startswith("--from="):
            args["date_from"] = arg.split("=", 1)[1]
        elif arg.startswith("--to="):
            args["date_to"] = arg.split("=", 1)[1]
    return args


def post(path, body):
    r = requests.post(BASE + path, headers=H, json=body, timeout=60)
    if r.status_code != 200:
        print(f"  [{r.status_code}] {path}: {r.text[:300]}")
        return None
    return r.json()


def get_types():
    data = post("/v1/finance/accrual/types", {})
    if not data:
        return {}
    types = {}
    for t in data.get("accrual_types") or data.get("result") or []:
        tid = t.get("id") or t.get("code")
        name = t.get("name") or t.get("title")
        if tid is not None:
            types[tid] = name
    return types


def fetch_day(date_str):
    """Возвращает все accruals за день (с пагинацией по last_id)."""
    all_rows = []
    last_id = ""
    for _ in range(200):
        body = {"date": date_str, "last_id": last_id}
        data = post("/v1/finance/accrual/by-day", body)
        if not data:
            break
        rows = data.get("accruals") or []
        if not rows:
            break
        all_rows.extend(rows)
        new_last = str(data.get("last_id") or "")
        if not new_last or new_last == last_id:
            break
        last_id = new_last
    return all_rows


def to_float(d):
    if not d:
        return None
    try:
        return float(d.get("amount") or 0)
    except (TypeError, ValueError, AttributeError):
        return None


def get_start_date(cur):
    row = cur.execute("SELECT MAX(date) FROM accruals").fetchone()
    max_date = row[0] if row else None
    if not max_date:
        return START_DEFAULT
    return (datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def save_accrual(cur, acc, types):
    accrual_id = acc.get("accrual_id")
    date_str = acc.get("date")
    if not accrual_id or not date_str:
        return 0, 0

    posting = acc.get("posting") or {}
    products = posting.get("products") or []
    schema = posting.get("delivery_schema")
    unit = acc.get("unit_number")
    category = acc.get("accrued_category")
    total = to_float(acc.get("total_amount"))

    raw_json_str = json.dumps(acc, ensure_ascii=False)

    n_acc = 0
    n_svc = 0

    # === 1. Основная запись в accruals ===
    # Если есть products — по одной на каждый SKU
    # Если нет — одна запись с sku=None
    if not products:
        cur.execute("""
            INSERT OR REPLACE INTO accruals
            (accrual_id, date, sku, unit_number, accrued_category, delivery_schema,
             seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount,
             raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (accrual_id, date_str, None, unit, category, schema,
              None, None, None, None, None, total, raw_json_str))
        n_acc += 1
    else:
        for p in products:
            sku = p.get("sku")
            comm = p.get("commission") or {}
            sp = to_float(comm.get("seller_price"))
            slp = to_float(comm.get("sale_price"))
            cm = to_float(comm.get("sale_commission") or comm.get("commission"))
            bn = to_float(comm.get("bonus"))
            ci = to_float(comm.get("coinvestment"))

            cur.execute("""
                INSERT OR REPLACE INTO accruals
                (accrual_id, date, sku, unit_number, accrued_category, delivery_schema,
                 seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount,
                 raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (accrual_id, date_str, sku, unit, category, schema,
                  sp, slp, cm, bn, ci, total, raw_json_str))
            n_acc += 1

            # Services внутри delivery
            delivery = p.get("delivery") or {}
            for svc in delivery.get("services") or []:
                tid = svc.get("type_id")
                amt = to_float(svc.get("accrued"))
                if tid is None or amt is None:
                    continue
                cur.execute("""
                    INSERT OR IGNORE INTO accruals_services
                    (accrual_id, date, sku, type_id, type_name, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (accrual_id, date_str, sku, tid,
                      types.get(tid, f"type_{tid}"), amt))
                n_svc += 1

    # === 2. non_item_fee — простой объект ===
    non_item = acc.get("non_item_fee")
    if non_item and isinstance(non_item, dict):
        tid = non_item.get("type_id")
        amt = to_float(non_item.get("accrued"))
        if tid is not None and amt is not None:
            cur.execute("""
                INSERT OR IGNORE INTO accruals_services
                (accrual_id, date, sku, type_id, type_name, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (accrual_id, date_str, None, tid,
                  types.get(tid, f"type_{tid}"), amt))
            n_svc += 1

    # === 3. item_fees — вложенная структура fees[].fees[] ===
    item_fees = acc.get("item_fees")
    if item_fees and isinstance(item_fees, dict):
        fee_groups = item_fees.get("fees") or []
        for group in fee_groups:
            sku = group.get("sku")
            inner_fees = group.get("fees") or []
            for fee in inner_fees:
                tid = fee.get("type_id")
                amt = to_float(fee.get("accrued"))
                if tid is None or amt is None:
                    continue
                cur.execute("""
                    INSERT OR IGNORE INTO accruals_services
                    (accrual_id, date, sku, type_id, type_name, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (accrual_id, date_str, sku, tid,
                      types.get(tid, f"type_{tid}"), amt))
                n_svc += 1

    # === 4. container_fees — на всякий случай ===
    container = acc.get("container_fees")
    if container and isinstance(container, dict):
        fees = container.get("fees") or []
        for fee in fees:
            tid = fee.get("type_id")
            amt = to_float(fee.get("accrued"))
            if tid is not None and amt is not None:
                cur.execute("""
                    INSERT OR IGNORE INTO accruals_services
                    (accrual_id, date, sku, type_id, type_name, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (accrual_id, date_str, None, tid,
                      types.get(tid, f"type_{tid}"), amt))
                n_svc += 1

    return n_acc, n_svc


def main():
    args = parse_args()
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ ФИНАНСОВ ИЗ OZON API")
    print("=" * 80)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Период
    if args["date_from"]:
        start = args["date_from"]
    else:
        start = get_start_date(cur)
    end = args["date_to"] or END

    print(f"\n[1] Период синхронизации: {start} — {end}")

    if start > end:
        print("  Данные уже актуальны.")
        con.close()
        return

    print("\n[2] Справочник типов начислений...")
    types = get_types()
    print(f"  Получено типов: {len(types)}")

    print(f"\n[3] Тянем по дням...")
    d = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    total_acc = 0
    total_svc = 0
    days_with_data = 0

    while d <= end_dt:
        ds = d.strftime("%Y-%m-%d")
        try:
            rows = fetch_day(ds)
        except Exception as e:
            print(f"  {ds}: ошибка — {e}")
            d += timedelta(days=1)
            continue

        if rows:
            days_with_data += 1
            for acc in rows:
                n_a, n_s = save_accrual(cur, acc, types)
                total_acc += n_a
                total_svc += n_s
            print(f"  {ds}: accruals={len(rows)}, товаров={total_acc}, услуг={total_svc}")
        d += timedelta(days=1)

    con.commit()

    print(f"\n[4] ИТОГИ:")
    print(f"  Дней с данными:    {days_with_data}")
    print(f"  Записей accruals:  {total_acc}")
    print(f"  Записей services:  {total_svc}")

    # Общая статистика по БД
    row = cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM accruals").fetchone()
    print(f"\n[5] В БД accruals:")
    print(f"  Всего записей: {row[0]}")
    print(f"  Период:        {row[1]} — {row[2]}")

    row = cur.execute("""
        SELECT SUM(sale_commission), SUM(bonus), SUM(coinvestment),
               SUM(seller_price), SUM(sale_price)
        FROM accruals WHERE date IS NOT NULL
    """).fetchone()
    if row and row[0] is not None:
        comm, bonus, ci, sp, slp = row
        print(f"\n[6] Финансы за весь период:")
        print(f"  seller_price:        {sp:>14,.2f} ₽")
        print(f"  sale_price:          {slp:>14,.2f} ₽")
        print(f"  sale_commission:     {comm:>14,.2f} ₽")
        print(f"  bonus:               {bonus:>14,.2f} ₽")
        print(f"  coinvestment:        {ci:>14,.2f} ₽")
        eff = (comm or 0) + (bonus or 0) + (ci or 0)
        print(f"  ЭФФЕКТ. КОМИССИЯ:    {eff:>14,.2f} ₽")
        if sp:
            print(f"  % от seller_price:   {eff / sp * 100:>14.2f}%")

    con.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
