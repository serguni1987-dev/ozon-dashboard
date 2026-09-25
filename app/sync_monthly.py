"""
sync_monthly.py - отчёт о реализации Ozon за предыдущий месяц.
Метод: POST /v2/finance/realization
"""
import os
import json
import requests
import sqlite3
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(APP_DIR, ".env")
DB = os.path.join(APP_DIR, "ozon.db")

load_dotenv(ENV_PATH)

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v2/finance/realization"
TAX_RATE = 0.15


def init_tables(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS monthly_reports (
        month            TEXT PRIMARY KEY,
        year             INTEGER,
        month_num        INTEGER,
        report_number    TEXT,
        report_date      TEXT,
        period_start     TEXT,
        period_end       TEXT,
        seller_price_sum     REAL DEFAULT 0,
        sale_price_sum       REAL DEFAULT 0,
        gross_commission_sum REAL DEFAULT 0,
        bonus_sum            REAL DEFAULT 0,
        coinvestment_sum     REAL DEFAULT 0,
        logistics_sum        REAL DEFAULT 0,
        total_held_sum       REAL DEFAULT 0,
        effective_fee_sum    REAL DEFAULT 0,
        stars_sum            REAL DEFAULT 0,
        tax_base             REAL DEFAULT 0,
        tax_15               REAL DEFAULT 0,
        net_profit           REAL DEFAULT 0,
        fetched_at           TEXT,
        raw_json             TEXT
    );

    CREATE TABLE IF NOT EXISTS monthly_realization_rows (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        month               TEXT NOT NULL,
        row_number          INTEGER,
        sku                 INTEGER,
        offer_id            TEXT,
        barcode             TEXT,
        item_name           TEXT,
        seller_price        REAL,
        sale_price          REAL,
        quantity            INTEGER,
        commission_ratio    REAL,
        gross_commission    REAL,
        bonus               REAL,
        coinvestment        REAL,
        logistics           REAL,
        total_held          REAL,
        effective_fee       REAL,
        stars               REAL,
        is_return           INTEGER DEFAULT 0,
        raw_json            TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_mrr_month ON monthly_realization_rows(month);
    CREATE INDEX IF NOT EXISTS idx_mrr_sku ON monthly_realization_rows(sku);
    """)
    con.commit()


def to_float(d):
    if d is None:
        return 0.0
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, dict):
        return float(d.get("amount") or 0)
    return 0.0


def main():
    print("=" * 80)
    print("ЗАГРУЗКА ОТЧЁТА О РЕАЛИЗАЦИИ ИЗ OZON API")
    print("=" * 80)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=None, help="YYYY-MM")
    parser.add_argument("--force", action="store_true",
                        help="Перезаписать уже загруженный месяц")
    args, _ = parser.parse_known_args()

    if args.month:
        parts = args.month.split("-")
        year = int(parts[0])
        month = int(parts[1])
        month_str = args.month
    else:
        today = date.today()
        prev = today - relativedelta(months=1)
        month = prev.month
        year = prev.year
        month_str = f"{year}-{month:02d}"

    print(f"\n[1] Запрашиваем отчёт за: {month_str}")

    body = {"month": month, "year": year}
    r = requests.post(URL, headers=H, json=body, timeout=120)

    print(f"    HTTP: {r.status_code}")
    if r.status_code != 200:
        print(f"    Ошибка: {r.text[:600]}")
        return

    data = r.json()
    result = data.get("result") or {}
    header = result.get("header") or {}
    rows = result.get("rows") or []

    print(f"    Строк в отчёте: {len(rows)}")
    print(f"    Номер отчёта: {header.get('number', '?')}")
    print(f"    Период: {header.get('start_date', '?')} - {header.get('stop_date', '?')}")

    if not rows:
        print("\n    Отчёт пустой.")
        return

    # Счётчики
    seller_price_sum = 0.0
    sale_price_sum = 0.0
    gross_commission_sum = 0.0
    bonus_sum = 0.0
    coinvestment_sum = 0.0
    logistics_sum = 0.0
    total_held_sum = 0.0
    effective_fee_sum = 0.0
    stars_sum = 0.0

    con = sqlite3.connect(DB)
    init_tables(con)

    # ── Проверка "уже загружено" ──
    existing = con.execute(
        "SELECT report_number, fetched_at FROM monthly_reports WHERE month = ?",
        (month_str,)
    ).fetchone()

    if existing and not args.force:
        print()
        print(f"[i] Месяц {month_str} уже загружен:")
        print(f"    Отчёт №{existing[0]}, загружен {existing[1]}")
        print(f"    Для перезаписи используй --force")
        print(f"    Или удали запись из monthly_reports вручную")
        con.close()
        return

    if existing and args.force:
        print()
        print(f"[!] --force: перезаписываю {month_str} (старый отчёт №{existing[0]})")

    con.execute("DELETE FROM monthly_realization_rows WHERE month = ?", (month_str,))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for row in rows:
        item = row.get("item") or {}
        dc = row.get("delivery_commission") or {}
        rc = row.get("return_commission") or {}

        sku = item.get("sku")
        offer_id = item.get("offer_id")
        barcode = item.get("barcode")
        item_name = item.get("name")
        seller_price = to_float(row.get("seller_price_per_instance"))
        commission_ratio = row.get("commission_ratio") or 0

        is_return = 1 if rc else 0

        # delivery_commission
        dc_sale_price = to_float(dc.get("price_per_instance"))
        dc_amount = to_float(dc.get("amount"))
        dc_qty = int(dc.get("quantity") or 0)
        dc_bonus = to_float(dc.get("bonus"))
        dc_std_fee = to_float(dc.get("standard_fee"))
        dc_total = to_float(dc.get("total"))
        dc_comm = to_float(dc.get("commission"))
        dc_comp = to_float(dc.get("compensation"))
        dc_bank_ci = to_float(dc.get("bank_coinvestment"))
        dc_pickup_ci = to_float(dc.get("pick_up_point_coinvestment"))
        dc_stars = to_float(dc.get("stars"))

        # return_commission
        rc_amount = to_float(rc.get("amount"))
        rc_bonus = to_float(rc.get("bonus"))
        rc_std_fee = to_float(rc.get("standard_fee"))
        rc_total = to_float(rc.get("total"))
        rc_comm = to_float(rc.get("commission"))
        rc_bank_ci = to_float(rc.get("bank_coinvestment"))
        rc_pickup_ci = to_float(rc.get("pick_up_point_coinvestment"))
        rc_stars = to_float(rc.get("stars"))

        # Итого по строке — delivery МИНУС return
        total_seller_price = seller_price * dc_qty
        total_sale_price = dc_amount - rc_amount
        total_bonus = dc_bonus - rc_bonus
        total_coinv = (dc_bank_ci + dc_pickup_ci) - (rc_bank_ci + rc_pickup_ci)
        total_gross_fee = dc_std_fee - rc_std_fee
        total_held = dc_total - rc_total
        total_logistics = total_held - total_gross_fee
        total_eff = total_held - total_bonus - total_coinv
        total_stars = dc_stars - rc_stars

        seller_price_sum += total_seller_price
        sale_price_sum += total_sale_price
        gross_commission_sum += total_gross_fee
        bonus_sum += total_bonus
        coinvestment_sum += total_coinv
        logistics_sum += total_logistics
        total_held_sum += total_held
        effective_fee_sum += total_eff
        stars_sum += total_stars

        con.execute("""
            INSERT INTO monthly_realization_rows
            (month, row_number, sku, offer_id, barcode, item_name,
             seller_price, sale_price, quantity, commission_ratio,
             gross_commission, bonus, coinvestment, logistics, total_held,
             effective_fee, stars, is_return, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month_str, row.get("rowNumber"), sku, offer_id, barcode, item_name,
            total_seller_price, total_sale_price, dc_qty, commission_ratio,
            total_gross_fee, total_bonus, total_coinv, total_logistics,
            total_held, total_eff, total_stars, is_return,
            json.dumps(row, ensure_ascii=False),
        ))

    # Вывод
    print(f"\n[2] СУММЫ ИЗ ОТЧЁТА:")
    print(f"    Seller price (ваша цена):       {seller_price_sum:>14,.2f} ₽")
    print(f"    Sale price (покупатель):        {sale_price_sum:>14,.2f} ₽")
    print(f"    Скидка Ozon (sp - slp):         {seller_price_sum - sale_price_sum:>14,.2f} ₽")
    print()
    print(f"    Гросс-комиссия Ozon:            {gross_commission_sum:>14,.2f} ₽")
    print(f"    Логистика (удержано сверх):     {logistics_sum:>14,.2f} ₽")
    print(f"    Итого удержано (total):         {total_held_sum:>14,.2f} ₽")
    print()
    print(f"    Баллы за скидки:                {bonus_sum:>14,.2f} ₽")
    print(f"    Соинвестирование:               {coinvestment_sum:>14,.2f} ₽")
    print(f"    Звёзды:                         {stars_sum:>14,.2f} ₽")
    print()
    print(f"    ЭФФЕКТИВНАЯ КОМИССИЯ:           {effective_fee_sum:>14,.2f} ₽")
    if seller_price_sum:
        print(f"    % от seller_price:              {effective_fee_sum/seller_price_sum*100:>14,.2f}%")

    print(f"\n    ПРОВЕРКА:")
    print(f"    bonus + coinvestment:           {bonus_sum + coinvestment_sum:>14,.2f} ₽")
    print(f"    seller_price - sale_price:      {seller_price_sum - sale_price_sum:>14,.2f} ₽")

    # Налог
    tax_base = sale_price_sum - bonus_sum
    tax_15 = tax_base * TAX_RATE
    net = seller_price_sum - effective_fee_sum - tax_15

    print(f"\n[3] НАЛОГ И ПРИБЫЛЬ:")
    print(f"    Налоговая база (sale - bonus):  {tax_base:>14,.2f} ₽")
    print(f"    Налог УСН 15%:                  {tax_15:>14,.2f} ₽")
    print(f"    Чистая прибыль:                 {net:>14,.2f} ₽")

    con.execute("""
        INSERT OR REPLACE INTO monthly_reports
        (month, year, month_num, report_number, report_date,
         period_start, period_end,
         seller_price_sum, sale_price_sum, gross_commission_sum,
         bonus_sum, coinvestment_sum, logistics_sum,
         total_held_sum, effective_fee_sum, stars_sum,
         tax_base, tax_15, net_profit, fetched_at, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        month_str, year, month,
        header.get("number"), header.get("doc_date"),
        header.get("start_date"), header.get("stop_date"),
        seller_price_sum, sale_price_sum, gross_commission_sum,
        bonus_sum, coinvestment_sum, logistics_sum,
        total_held_sum, effective_fee_sum, stars_sum,
        tax_base, tax_15, net,
        now_str, json.dumps(header, ensure_ascii=False),
    ))
    con.commit()

    n_rows = con.execute(
        "SELECT COUNT(*) FROM monthly_realization_rows WHERE month = ?",
        (month_str,)
    ).fetchone()[0]
    print(f"\n[4] Сохранено:")
    print(f"    monthly_reports:          1 запись ({month_str})")
    print(f"    monthly_realization_rows: {n_rows} строк")

    con.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
