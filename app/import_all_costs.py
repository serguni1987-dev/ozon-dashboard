"""
import_all_costs.py — импорт себестоимости из costs_all.csv.
Обновляет products.cost_price по offer_id (и по sku, если offer_id нет).
Устойчив к: пустым строкам, пробелам, запятым, ₽, тексту.
"""
import csv
import re
import sqlite3

DB = "ozon.db"
CSV_FILE = "costs_all.csv"


def to_money(v):
    """'3 500' / '3500,50' / '3500 ₽' → float или None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s in {"-", "–", "—", "None", "nan"}:
        return None
    s = s.replace("₽", "").replace("\u00A0", "").replace(" ", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    with open(CSV_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    print(f"Прочитано строк: {len(rows)}")
    print(f"Колонки: {list(rows[0].keys()) if rows else '—'}")

    con = sqlite3.connect(DB)
    cur = con.cursor()

    updated_by_offer = 0
    updated_by_sku = 0
    skipped_no_cost = 0
    skipped_not_found = 0
    errors = 0

    for i, r in enumerate(rows, 1):
        offer_id = (r.get("offer_id") or "").strip()
        sku_raw = (r.get("sku") or "").strip()
        cost = to_money(r.get("cost_price"))

        if cost is None or cost <= 0:
            skipped_no_cost += 1
            continue

        found = False

        if offer_id:
            cur.execute(
                "UPDATE products SET cost_price = ? WHERE offer_id = ?",
                (cost, offer_id)
            )
            if cur.rowcount > 0:
                updated_by_offer += cur.rowcount
                found = True

        if not found and sku_raw:
            try:
                sku = int(float(sku_raw))
                cur.execute(
                    "UPDATE products SET cost_price = ? WHERE sku = ?",
                    (cost, sku)
                )
                if cur.rowcount > 0:
                    updated_by_sku += cur.rowcount
                    found = True
            except ValueError:
                pass

        if not found:
            skipped_not_found += 1
            if skipped_not_found <= 10:
                print(f"  [WARN] строка {i}: не найден offer_id={offer_id!r} sku={sku_raw!r}")

    con.commit()

    print()
    print("=" * 70)
    print(f"  Обновлено по offer_id:   {updated_by_offer}")
    print(f"  Обновлено по sku:        {updated_by_sku}")
    print(f"  Пропущено (нет цены):    {skipped_no_cost}")
    print(f"  Не найдено в products:   {skipped_not_found}")
    print(f"  Ошибок:                  {errors}")
    print("=" * 70)

    # Финальная статистика
    total = con.execute("SELECT COUNT(*) FROM products WHERE is_own = 1").fetchone()[0]
    with_cost = con.execute(
        "SELECT COUNT(*) FROM products WHERE is_own = 1 AND cost_price IS NOT NULL AND cost_price > 0"
    ).fetchone()[0]
    print(f"\n  Своих SKU всего:                 {total}")
    print(f"  С себестоимостью:                {with_cost}")
    print(f"  Без себестоимости:               {total - with_cost}")

    con.close()


if __name__ == "__main__":
    main()
