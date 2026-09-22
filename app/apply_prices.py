"""
apply_prices.py — массовое обновление цен через Ozon API.
Читает actions.csv, берёт категорию УБЫТОЧНЫЙ (или --category=...).

Режимы:
  py apply_prices.py                       # dry-run
  py apply_prices.py --apply               # реальное обновление
  py apply_prices.py --apply --only=OCE013E4   # только один SKU
  py apply_prices.py --rollback 5          # откатить изменение id=5

Защита:
  - Не менять цену чаще 10 раз/час на SKU (лимит Ozon)
  - min_price = new_price * 0.9 (защита от снижения Ozon)
  - Все изменения логируются в price_changes
  - Запись в decisions для дневника

API: /v1/product/import/prices
"""
import os
import sys
import csv
import json
import uuid
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
URL = "https://api-seller.ozon.ru/v1/product/import/prices"
DB = "ozon.db"
ACTIONS = "actions.csv"

TARGET_MARGIN = 0.08
COMMISSION_PCT = 0.0281
SERVICES_PCT = 0.142

# Лимит Ozon: 10 изменений цены в час на SKU
RATE_LIMIT_PER_HOUR = 10
# Минимальный интервал между изменениями одного SKU (защита)
MIN_HOURS_BETWEEN = 1


def calc_target_price(cost_price, current_price):
    denom = 1 - COMMISSION_PCT - SERVICES_PCT - TARGET_MARGIN
    ideal = cost_price / denom if denom > 0 else current_price
    cap = current_price * 1.20
    return min(ideal, cap)


def parse_args():
    args = {"dry_run": True, "categories": set(), "only": None, "rollback_id": None}
    for arg in sys.argv[1:]:
        if arg == "--apply":
            args["dry_run"] = False
        elif arg.startswith("--category="):
            args["categories"].add(arg.split("=", 1)[1])
        elif arg.startswith("--only="):
            args["only"] = arg.split("=", 1)[1]
        elif arg.startswith("--rollback"):
            # --rollback 5 или --rollback=5
            if "=" in arg:
                args["rollback_id"] = arg.split("=", 1)[1]
            else:
                # следующий аргумент
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    args["rollback_id"] = sys.argv[idx + 1]
    if not args["categories"]:
        args["categories"] = {"УБЫТОЧНЫЙ"}
    return args


def check_rate_limit(con, offer_id, hours=MIN_HOURS_BETWEEN):
    """Проверяет, менялась ли цена за последние N часов."""
    threshold = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    row = con.execute("""
        SELECT COUNT(*) FROM price_changes
        WHERE offer_id = ? AND changed_at > ? AND api_status = 'ok'
    """, (offer_id, threshold)).fetchone()
    return row[0] if row else 0


def log_change(con, offer_id, sku, old_price, new_price, min_price,
               status, message, batch_id):
    con.execute("""
        INSERT INTO price_changes
        (changed_at, offer_id, sku, old_price, new_price, min_price,
         api_status, api_message, batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        offer_id, sku, old_price, new_price, min_price,
        status, message, batch_id,
    ))


def add_decision(con, offer_id, old_price, new_price, batch_id):
    """Запись в decisions для дневника."""
    prod = con.execute(
        "SELECT sku, cost_price FROM products WHERE offer_id = ?", (offer_id,)
    ).fetchone()
    if not prod:
        return
    sku, cost_price = prod

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    agg = con.execute("""
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts
        FROM sales_daily WHERE sku = ? AND date BETWEEN ? AND ?
    """, (sku, date_from, max_date)).fetchone()

    price_row = con.execute("""
        SELECT AVG(avg_price) AS p FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ? AND orders_units > 0
    """, (sku, date_from, max_date)).fetchone()

    rev = agg["rev"] or 0
    orders = agg["orders"] or 0
    cost = (cost_price or 0) * orders
    comm = rev * COMMISSION_PCT
    serv = rev * SERVICES_PCT
    pb = rev - cost - comm - serv
    tax = pb * 0.15 if pb > 0 else 0
    profit = pb - tax
    margin = profit / rev if rev else 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    review_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    con.execute("""
        INSERT INTO decisions
        (created_at, offer_id, category, action_text,
         revenue_before, profit_before, margin_before, orders_before,
         views_before, carts_before, price_before, price_after,
         status, review_at, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?)
    """, (
        now, offer_id, "УБЫТОЧНЫЙ",
        f"Поднял цену с {old_price:,.0f} до {new_price:,.0f} ₽ (apply_prices)",
        rev, profit, margin, orders,
        agg["views"] or 0, agg["carts"] or 0,
        price_row["p"] if price_row and price_row["p"] else old_price,
        new_price,
        review_at, f"batch_id={batch_id}",
    ))


def do_rollback(con, rollback_id):
    """Откат одного изменения цены."""
    row = con.execute("""
        SELECT id, offer_id, sku, old_price, new_price, api_status, rolled_back
        FROM price_changes WHERE id = ?
    """, (rollback_id,)).fetchone()

    if not row:
        print(f"[ERROR] Изменение id={rollback_id} не найдено")
        return

    pid, offer_id, sku, old_price, new_price, status, rolled = row
    if rolled:
        print(f"[SKIP] id={pid} уже откатан")
        return
    if status != "ok":
        print(f"[ERROR] id={pid}: статус '{status}', нечего откатывать")
        return

    print(f"Откатываю: {offer_id}: {new_price:,.0f} → {old_price:,.0f} ₽")
    body = {"prices": [{
        "offer_id": offer_id,
        "price": f"{old_price:.2f}",
        "old_price": f"{old_price:.2f}",
        "min_price": f"{old_price * 0.9:.2f}",
        "currency_code": "RUB",
        "auto_action_enabled": "UNKNOWN",
    }]}

    r = requests.post(URL, headers=H, json=body, timeout=60)
    if r.status_code != 200:
        print(f"  ОШИБКА: {r.text[:500]}")
        return

    data = r.json()
    results = data.get("result") or []
    ok = any(item.get("updated") for item in results)
    if ok:
        con.execute("""
            UPDATE price_changes
            SET rolled_back = 1, rollback_at = ?
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pid))
        con.commit()
        print(f"  [OK] Откат применён")
    else:
        err = results[0].get("errors", [{}])[0].get("message", "unknown") if results else "empty result"
        print(f"  [FAIL] {err}")


def main():
    args = parse_args()
    dry_run = args["dry_run"]
    categories = args["categories"]
    only = args["only"]
    rollback_id = args["rollback_id"]

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # === ROLLBACK ===
    if rollback_id:
        do_rollback(con, int(rollback_id))
        con.close()
        return

    batch_id = str(uuid.uuid4())[:8]

    print("=" * 100)
    mode = "DRY-RUN (без изменений)" if dry_run else "*** APPLY — реальное обновление ***"
    print(f"ОБНОВЛЕНИЕ ЦЕН  |  режим: {mode}")
    print(f"Категории: {', '.join(sorted(categories))}")
    if only:
        print(f"Только SKU: {only}")
    if not dry_run:
        print(f"Batch ID: {batch_id}")
    print("=" * 100)

    # 1. Читаем actions.csv
    with open(ACTIONS, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = [r for r in reader if r.get("категория") in categories]

    if only:
        rows = [r for r in rows if r.get("offer_id") == only]
        if not rows:
            print(f"\nSKU {only} не найден в actions.csv в указанных категориях.")
            con.close()
            return

    if not rows:
        print("\nНет SKU в указанных категориях.")
        con.close()
        return

    print(f"\nSKU к обработке: {len(rows)}")

    # 2. Готовим обновления
    updates = []
    skipped_rate = []
    skipped_already = []
    skipped_notfound = []

    for r in rows:
        oid = r["offer_id"]
        prod = con.execute(
            "SELECT sku, cost_price FROM products WHERE offer_id = ?", (oid,)
        ).fetchone()
        if not prod:
            skipped_notfound.append(oid)
            continue

        price_row = con.execute("""
            SELECT AVG(avg_price) AS p FROM sales_daily
            WHERE sku = ? AND orders_units > 0
        """, (prod["sku"],)).fetchone()
        cur_price = price_row["p"] if price_row and price_row["p"] else None

        if not cur_price:
            skipped_notfound.append(oid)
            continue

        cost = prod["cost_price"] or 0
        target = calc_target_price(cost, cur_price)

        if target <= cur_price * 1.01:
            skipped_already.append(oid)
            continue

        # Проверка лимита: если уже менялось за последний час — пропускаем
        n_changes = check_rate_limit(con, oid)
        if n_changes > 0:
            skipped_rate.append((oid, n_changes))
            continue

        updates.append({
            "offer_id": oid,
            "sku": prod["sku"],
            "cost": cost,
            "current": cur_price,
            "target": target,
            "delta_pct": (target / cur_price - 1) * 100,
        })

    # 3. Показываем план
    if updates:
        print(f"\n{'Offer ID':<18} {'Себест':>8} {'Сейчас':>10} {'Цель':>10} {'Δ%':>7}  {'Лимит'}")
        print("-" * 75)
        for u in updates:
            n = check_rate_limit(con, u["offer_id"])
            limit_note = f"{n}/10 за час" if n else "ок"
            print(f"{u['offer_id']:<18} {u['cost']:>8,.0f} {u['current']:>10,.0f} "
                  f"{u['target']:>10,.0f} {u['delta_pct']:>+6.1f}%  {limit_note}")

    if skipped_rate:
        print(f"\n[!] Пропущено из-за лимита (не чаще 1 раза в час на SKU):")
        for item in skipped_rate:
            print(f"    {item[0]}: уже менялось {item[1]} раз(а) за час — пропуск")

    if skipped_already:
        print(f"\n[i] Уже >= целевой цены: {len(skipped_already)}")
    if skipped_notfound:
        print(f"\n[i] Не найдены / нет истории цен: {len(skipped_notfound)}")

    if not updates:
        print("\nНечего обновлять.")
        con.close()
        return

    if dry_run:
        print("\n" + "=" * 100)
        print("  DRY-RUN. Ничего не отправлено в Ozon.")
        print(f"  Для реального обновления: py apply_prices.py --apply")
        if not only:
            print(f"  Для теста на одном SKU:  py apply_prices.py --apply --only={updates[0]['offer_id']}")
        print("=" * 100)
        con.close()
        return

    # 4. Отправляем в Ozon (LIVE)
    print(f"\n[3] Отправляю в Ozon ({len(updates)} SKU)  batch_id={batch_id}...")

    body = {
        "prices": [
            {
                "offer_id": u["offer_id"],
                "price": f"{u['target']:.2f}",
                "old_price": f"{u['target']:.2f}",
                "min_price": f"{u['target'] * 0.9:.2f}",
                "currency_code": "RUB",
                "auto_action_enabled": "UNKNOWN",
            }
            for u in updates
        ]
    }

    r = requests.post(URL, headers=H, json=body, timeout=60)
    print(f"  HTTP: {r.status_code}")

    if r.status_code != 200:
        print(f"  ОШИБКА: {r.text[:1000]}")
        # Логируем неудачу
        for u in updates:
            log_change(con, u["offer_id"], u["sku"], u["current"], u["target"],
                       u["target"] * 0.9, "error", f"HTTP {r.status_code}", batch_id)
        con.commit()
        con.close()
        return

    data = r.json()
    results = data.get("result") or []
    results_by_offer = {item.get("offer_id"): item for item in results}

    print(f"  Получено результатов: {len(results)}")
    print()
    print(f"  {'Offer ID':<18} {'Статус':<8} {'Сообщение'}")
    print("  " + "-" * 70)

    ok_count = 0
    fail_count = 0

    for u in updates:
        item = results_by_offer.get(u["offer_id"], {})
        updated = item.get("updated", False)
        errors = item.get("errors") or []
        err_msg = errors[0].get("message", "") if errors else ""

        status = "OK" if updated else "FAIL"
        if updated:
            ok_count += 1
        else:
            fail_count += 1

        print(f"  {u['offer_id']:<18} {status:<8} {err_msg[:50]}")

        # Логируем
        log_change(con, u["offer_id"], u["sku"], u["current"], u["target"],
                   u["target"] * 0.9, "ok" if updated else "error",
                   err_msg, batch_id)

        # Записываем в decisions только успешные
        if updated:
            try:
                add_decision(con, u["offer_id"], u["current"], u["target"], batch_id)
            except Exception as e:
                print(f"    [WARN] decisions: {e}")

    con.commit()

    # Сохраняем полный лог
    with open("apply_prices_log.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 100)
    print(f"  ОБНОВЛЕНО: {ok_count}   ОШИБОК: {fail_count}")
    print(f"  Batch ID: {batch_id}")
    print(f"  Лог:      apply_prices_log.json")
    print(f"  В decisions: добавлено {ok_count} записей")
    print(f"  Откат:    py apply_prices.py --rollback <id из price_changes>")
    print("=" * 100)

    con.close()


if __name__ == "__main__":
    main()
