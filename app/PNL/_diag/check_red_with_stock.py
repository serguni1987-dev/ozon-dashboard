import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

rows = con.execute("""
    SELECT cp.offer_id, p.name, cp.price, cp.min_price,
           COALESCE(cs.total_present, 0) AS stock,
           p.cost_price
    FROM current_prices cp
    JOIN products p ON p.offer_id = cp.offer_id
    LEFT JOIN current_stocks cs ON cs.offer_id = cp.offer_id
    WHERE cp.price_index_color = 'RED'
      AND p.is_own = 1 AND p.is_archived = 0
      AND p.sku NOT IN (
          SELECT DISTINCT sku FROM sales_daily
          WHERE date >= '2026-08-21' AND orders_units > 0
      )
""").fetchall()

zero = [r for r in rows if (r["stock"] or 0) == 0]
positive = [r for r in rows if (r["stock"] or 0) > 0]

print(f"RED + без продаж: всего {len(rows)}")
print(f"  Остаток = 0:      {len(zero)}")
print(f"  Остаток > 0:      {len(positive)}")

if positive:
    print(f"\n🔴 RED + ЕСТЬ ОСТАТОК ({len(positive)}) — это реальная проблема цены:")
    print(f"  {'Offer ID':<18} {'Цена':>8} {'Min':>8} {'Остаток':>8} {'Себест':>8}")
    print("  " + "-" * 55)
    for r in sorted(positive, key=lambda x: -x["stock"])[:30]:
        print(f"  {r['offer_id']:<18} {r['price']:>8,.0f} {r['min_price'] or 0:>8,.0f} "
              f"{r['stock']:>8} {r['cost_price'] or 0:>8,.0f}")

if zero:
    frozen_value = sum((r["cost_price"] or 0) * (r["stock"] or 0) for r in zero)
    print(f"\n⚪ RED + остаток 0 ({len(zero)}) — товара нет на складе")
    print(f"   Заморожено в них: {frozen_value:,.0f} ₽")

con.close()
