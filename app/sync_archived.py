"""
sync_archived.py — синхронизация архива с Ozon.
/v3/product/list с visibility ALL не возвращает архивные,
поэтому запрашиваем отдельно ARCHIVED и ALL.
"""
import os
import requests
import sqlite3
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v3/product/list"
DB = "ozon.db"


def fetch_all(visibility):
    """Постранично тянет товары с указанным visibility."""
    all_items = []
    last_id = ""
    page = 1
    while True:
        body = {"filter": {"visibility": visibility}, "last_id": last_id, "limit": 1000}
        r = requests.post(URL, headers=H, json=body, timeout=60)
        if r.status_code != 200:
            print(f"  [{r.status_code}] visibility={visibility}: {r.text[:300]}")
            break
        data = r.json()
        result = data.get("result") or {}
        items = result.get("items") or []
        if not items:
            break
        all_items.extend(items)
        print(f"  {visibility} стр.{page}: +{len(items)}, всего {len(all_items)}")
        last_id = result.get("last_id") or ""
        if not last_id:
            break
        page += 1
        if page > 50:
            break
    return all_items


def main():
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ АРХИВА С OZON")
    print("=" * 80)

    print("\n[1] Забираем ВСЕ товары (visibility=ALL)...")
    all_items = fetch_all("ALL")
    print(f"  Всего: {len(all_items)}")

    print("\n[2] Забираем АРХИВНЫЕ (visibility=ARCHIVED)...")
    arch_items = fetch_all("ARCHIVED")
    print(f"  Всего: {len(arch_items)}")

    # Объединяем по offer_id: приоритет у ARCHIVED
    by_offer = {}
    for it in all_items:
        oid = it.get("offer_id")
        if oid:
            by_offer[oid] = it.get("archived", False)
    for it in arch_items:
        oid = it.get("offer_id")
        if oid:
            by_offer[oid] = True

    archived_ids = {oid for oid, arch in by_offer.items() if arch}
    active_ids = {oid for oid, arch in by_offer.items() if not arch}

    print(f"\n  Активных на Ozon:  {len(active_ids)}")
    print(f"  В архиве на Ozon:  {len(archived_ids)}")

    # Обновляем базу
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("UPDATE products SET is_archived = 0")
    print(f"\n[3] Сброшено is_archived у {cur.rowcount} SKU")

    updated = 0
    for oid in archived_ids:
        cur.execute("UPDATE products SET is_archived = 1 WHERE offer_id = ?", (oid,))
        updated += cur.rowcount
    con.commit()
    print(f"  Помечено архивными: {updated}")

    print("\n[4] ИТОГИ в базе:")
    total_own = cur.execute("SELECT COUNT(*) FROM products WHERE is_own = 1").fetchone()[0]
    arch_own = cur.execute(
        "SELECT COUNT(*) FROM products WHERE is_own = 1 AND is_archived = 1"
    ).fetchone()[0]
    print(f"  Своих SKU:            {total_own}")
    print(f"  Из них в архиве:      {arch_own}")
    print(f"  Активных для анализа: {total_own - arch_own}")

    print("\n[5] Первые 20 архивных в базе:")
    for (oid,) in cur.execute(
        "SELECT offer_id FROM products WHERE is_archived = 1 ORDER BY offer_id LIMIT 20"
    ):
        print(f"  {oid}")

    # Архивные на Ozon, но не в базе
    known = {r[0] for r in cur.execute("SELECT offer_id FROM products")}
    missing = sorted(archived_ids - known)
    if missing:
        print(f"\n[6] Архивных на Ozon, но НЕ в базе: {len(missing)}")
        for oid in missing[:20]:
            print(f"  {oid}")

    con.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
