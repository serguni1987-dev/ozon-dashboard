"""migrate_costs_csv.py — создаёт новый costs_all.csv в проект/ с колонкой date_from.
Формат: offer_id;sku;name;category_l2;cost_price;date_from;comment
Переносит данные из старого app/costs_all.csv + продуктов.
"""
import csv, sqlite3, os

# ── Пути ──
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)          # = проект/
OLD_CSV = os.path.join(APP_DIR, "costs_all.csv")
NEW_CSV = os.path.join(PROJECT_DIR, "costs_all.csv")

print(f"APP_DIR:     {APP_DIR}")
print(f"PROJECT_DIR: {PROJECT_DIR}")
print(f"Старый CSV:  {OLD_CSV}")
print(f"Новый CSV:   {NEW_CSV}")
print()

# ── 1. Читаю старый CSV (offer_id;sku;name;category_l2;revenue_period;orders_period;cost_price;comment) ──
old_data = {}
if os.path.exists(OLD_CSV):
    with open(OLD_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            offer = (row.get("offer_id") or "").strip()
            if offer:
                old_data[offer] = row
    print(f"[OK] Прочитан старый CSV: {len(old_data)} строк")
else:
    print(f"[!] Старый CSV не найден: {OLD_CSV}")

# ── 2. Тяну продукты из БД ──
c = sqlite3.connect(os.path.join(APP_DIR, "ozon.db"))
c.row_factory = sqlite3.Row

products = list(c.execute("""
    SELECT sku, offer_id, name, category_l2, cost_price
    FROM products
    WHERE is_own = 1
    ORDER BY offer_id
"""))
print(f"[OK] Продуктов is_own=1: {len(products)}")

# ── 3. Записываю новый CSV ──
with open(NEW_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["offer_id", "sku", "name", "category_l2",
                "cost_price", "date_from", "comment"])
    written = 0
    for p in products:
        offer = p["offer_id"] or ""
        old = old_data.get(offer, {})
        w.writerow([
            offer,
            p["sku"],
            (p["name"] or "")[:200],
            p["category_l2"] or "",
            f"{p['cost_price']:.2f}" if p["cost_price"] else "",
            "2026-01-01",
            "",
        ])
        written += 1

print(f"[OK] Записано в {NEW_CSV}: {written} строк")

# ── 4. Проверка ──
print()
print("=== Первые 3 строки нового файла ===")
with open(NEW_CSV, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f, delimiter=";")
    for i, r in enumerate(reader):
        if i > 3:
            break
        print(f"  {r}")

c.close()
print()
print("[OK] Готово")