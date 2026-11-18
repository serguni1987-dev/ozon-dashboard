"""
sync_finance.py — синхронизация финансовых начислений из Ozon API.

Тянет /v1/finance/accrual/by-day с последней даты в БД (или с 2026-09-01).
Идемпотентно: повторный запуск не создаёт дублей.

Фикс от 2026-10-09: добавлен блок 5 — сиротские записи
(нет posting, нет item_fees/non_item_fee/container_fees),
которые раньше терялись. Это штрафы, страхование, компенсации —
пишутся с type_id=0 и именем из accrued_category.
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
DB = os.path.join(os.getenv("PULT_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "ozon.db")

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
        raise RuntimeError(f"Ozon API HTTP {r.status_code}: {path}")
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Ozon API returned a non-object response: {path}")
    return data


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
    """Return a complete day or raise; never return partial pages after failure."""
    all_rows = []
    last_id = ""
    seen = set()
    for _ in range(200):
        data = post("/v1/finance/accrual/by-day", {"date": date_str, "last_id": last_id})
        if not isinstance(data, dict) or "accruals" not in data:
            raise RuntimeError(f"Invalid accrual response for {date_str}")
        rows = data["accruals"]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError(f"Invalid accrual rows for {date_str}")
        new_last = str(data.get("last_id") or "")
        if not rows:
            if new_last:
                raise RuntimeError(f"Empty page with continuation for {date_str}")
            return all_rows
        all_rows.extend(rows)
        if not new_last:
            return all_rows
        if new_last == last_id or new_last in seen:
            raise RuntimeError(f"Repeated pagination cursor for {date_str}")
        seen.add(new_last)
        last_id = new_last
    raise RuntimeError(f"Pagination limit exceeded for {date_str}")


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
    return (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")


def save_accrual(cur,acc,types):
    from pathlib import Path
    root=str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:sys.path.insert(0,root)
    from unitka.accrual_detail import save_accrual_record
    return save_accrual_record(cur,acc,types)


def main():
    from pathlib import Path
    root=str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:sys.path.insert(0,root)
    from unitka.finance_ingestion import validated_day
    from unitka.ingestion_safety import span
    args = parse_args()
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ ФИНАНСОВ ИЗ OZON API")
    print("=" * 80)

    if not Path(DB).is_file():
        raise FileNotFoundError("Configured database does not exist")
    con = sqlite3.connect(Path(DB).resolve().as_uri()+"?mode=rw", uri=True)
    try:
        with con:
            cur = con.cursor()

            # Период
            if args["date_from"]:
                start = args["date_from"]
            else:
                start = get_start_date(cur)
            end = args["date_to"] or END

            print(f"\n[1] Период синхронизации: {start} — {end}")

            span(start,end)

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
                rows = fetch_day(ds)
                validated_day(rows,ds)

                if rows:
                    days_with_data += 1
                    for acc in rows:
                        n_a, n_s = save_accrual(cur, acc, types)
                        total_acc += n_a
                        total_svc += n_s
                    print(f"  {ds}: accruals={len(rows)}, товаров={total_acc}, услуг={total_svc}")
                d += timedelta(days=1)


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

            print("\n" + "=" * 80)
    finally:
        con.close()


if __name__ == "__main__":
    main()
