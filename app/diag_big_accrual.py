"""
diag_big_accrual.py — ищем крупные записи и смотрим их raw.
"""
import os
import json
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 80)
print("ЗАПИСИ > 100 РУБ ЗА АВГУСТ — С RAW")
print("=" * 80)

# Сначала — что за записи без SKU
print("\n[1] ЗАПИСИ БЕЗ SKU (sku=None):")
rows = con.execute("""
    SELECT accrual_id, date, accrued_category, delivery_schema,
           total_amount, raw_json
    FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND sku IS NULL
    ORDER BY ABS(total_amount) DESC
    LIMIT 20
""").fetchall()

print(f"    Найдено: {len(rows)}")
for r in rows:
    print(f"    {r['accrual_id']:<15} {r['date']:<12} {str(r['accrued_category']):<15} "
          f"schema={str(r['delivery_schema']):<5} total={r['total_amount']:>10,.2f}")

# Разбор первых 5 — смотрим raw
print("\n[2] РАЗБОР RAW ДЛЯ ПЕРВЫХ 5:")
for r in rows[:5]:
    print(f"\n--- Accrual {r['accrual_id']} ({r['date']}) ---")
    print(f"    Total: {r['total_amount']:.2f}")
    try:
        data = json.loads(r["raw_json"])
        print(f"    Ключи raw: {list(data.keys())}")
        # Показываем item_fees / non_item_fee / container_fees
        for k in ["item_fees", "non_item_fee", "container_fees"]:
            v = data.get(k)
            if v:
                print(f"\n    {k}:")
                print(f"      {json.dumps(v, ensure_ascii=False, indent=6)[:1500]}")
        # И posting
        p = data.get("posting")
        if p:
            print(f"\n    posting.delivery_schema: {p.get('delivery_schema')}")
            prods = p.get("products") or []
            print(f"    posting.products: {len(prods)} шт")
    except Exception as e:
        print(f"    Ошибка: {e}")

# Дальше — все крупные записи с расхождением
print("\n" + "=" * 80)
print("КРУПНЫЕ ЗАПИСИ С РАСХОЖДЕНИЕМ")
print("=" * 80)

rows = con.execute("""
    SELECT a.accrual_id, a.date, a.sku, a.accrued_category,
           a.delivery_schema, a.total_amount,
           (SELECT SUM(amount) FROM accruals_services s
            WHERE s.accrual_id = a.accrual_id) AS services_sum,
           (SELECT COUNT(*) FROM accruals_services s
            WHERE s.accrual_id = a.accrual_id) AS n_services
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND ABS(a.total_amount) > 100
    ORDER BY ABS(a.total_amount) DESC
""").fetchall()

print(f"\nВсего крупных записей: {len(rows)}")
print(f"\n{'Accrual ID':<15} {'Date':<12} {'SKU':<15} {'Category':<12} {'Total':>10} {'Services':>10} {'N':>3}")
print("-" * 90)

problem_total = 0
for r in rows:
    s_sum = r["services_sum"] or 0
    delta = r["total_amount"] - s_sum
    if r["n_services"] == 0 or abs(delta) > 1:
        sku_str = str(r["sku"]) if r["sku"] else "None"
        print(f"{r['accrual_id']:<15} {r['date']:<12} {sku_str:<15} "
              f"{str(r['accrued_category']):<12} {r['total_amount']:>10,.2f} "
              f"{s_sum:>10,.2f} {r['n_services']:>3}")
        problem_total += delta

print("-" * 90)
print(f"Сумма расхождений: {problem_total:,.2f}")

con.close()
