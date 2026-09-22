"""
worklist.py — рабочий список на сегодня.
Показывает только те SKU, где есть что делать:
  - мёртвые с потенциалом (pdp >= 30, заказов 0)
  - звёзды (маржа >= 25%) — масштабировать
  - критическая маржа (< 5%) — цена
Плюс общий счётчик «потенциальная выручка».
"""
import sqlite3
from datetime import datetime, timedelta

DB = "ozon.db"

COMMISSION_PCT = 0.03
SERVICES_PCT   = 0.06
TAX_PCT        = 0.15

PDP_HOT = 30
AVG_CHECK = 6285  # средний чек по магазину


def money(x):
    return f"{x:>10,.0f} ₽"


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    # --- 1. Мёртвые с потенциалом ---
    dead_hot = con.execute("""
        SELECT p.offer_id, p.name,
               SUM(sd.views_total)   AS views,
               SUM(sd.pdp_visits)    AS pdp,
               MAX(sd.price_index)   AS price_idx,
               MAX(sd.stock)         AS stock
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
        HAVING SUM(sd.orders_units) = 0
           AND SUM(sd.pdp_visits) >= ?
        ORDER BY pdp DESC
    """, (date_from, max_date, PDP_HOT)).fetchall()

    # --- 2. Звёзды ---
    stars = con.execute("""
        SELECT p.offer_id, p.name, p.cost_price,
               SUM(sd.revenue)       AS revenue,
               SUM(sd.orders_units)  AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
        HAVING SUM(sd.orders_units) > 0
    """, (date_from, max_date)).fetchall()

    star_list = []
    for r in stars:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        cost = (r["cost_price"] or 0) * orders
        comm = rev * COMMISSION_PCT
        serv = rev * SERVICES_PCT
        pb = rev - cost - comm - serv
        tx = pb * TAX_PCT if pb > 0 else 0
        profit = pb - tx
        margin = profit / rev if rev else 0
        if margin >= 0.25:
            star_list.append((r, profit, margin))
    star_list.sort(key=lambda x: -x[1])

    # --- 3. Критическая маржа ---
    crit_list = []
    for r in stars:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        cost = (r["cost_price"] or 0) * orders
        comm = rev * COMMISSION_PCT
        serv = rev * SERVICES_PCT
        pb = rev - cost - comm - serv
        tx = pb * TAX_PCT if pb > 0 else 0
        profit = pb - tx
        margin = profit / rev if rev else 0
        if margin < 0.05:
            cur_price = rev / orders if orders else 0
            denom = 1 - COMMISSION_PCT - SERVICES_PCT - 0.15
            need = (r["cost_price"] or 0) / denom if denom > 0 else 0
            crit_list.append((r, profit, margin, cur_price, need))
    crit_list.sort(key=lambda x: x[2])

    # --- Вывод ---
    print("=" * 118)
    print(f"РАБОЧИЙ СПИСОК НА СЕГОДНЯ   |   период {date_from} — {max_date}")
    print("=" * 118)
    print()

    print(f"  [1] МЁРТВЫЕ С ПОТЕНЦИАЛОМ  ({len(dead_hot)} SKU)  — заходят, но не покупают")
    print(f"      Действие: переделать карточку (фото, описание, видео, отзывы)")
    print("  " + "-" * 114)
    if dead_hot:
        total_pdp = 0
        for r in dead_hot:
            pdp = r["pdp"] or 0
            total_pdp += pdp
            name = (r["name"] or "")[:45]
            price = (r["price_idx"] or "—")[:14]
            print(f"    {r['offer_id']:<18} {name:<45} заходов {pdp:>4}  цена {price:<14} ост {r['stock']}")
        potential = total_pdp * 0.01 * AVG_CHECK
        print(f"\n    Всего заходов без покупки: {total_pdp}")
        print(f"    При конверсии 1% и среднем чеке {AVG_CHECK:,} ₽: "
              f"потенциал ≈ {potential:,.0f} ₽")
    else:
        print("    нет")
    print()

    print(f"  [2] ЗВЁЗДЫ  ({len(star_list)} SKU)  — маржа >= 25%, масштабировать")
    print(f"      Действие: включить в акции, бустинг, пополнить остатки")
    print("  " + "-" * 114)
    if star_list:
        for r, profit, margin in star_list[:10]:
            name = (r["name"] or "")[:45]
            print(f"    {r['offer_id']:<18} {name:<45} "
                  f"маржа {margin*100:>5.1f}%  приб {money(profit)}  зак {r['orders']}")
    else:
        print("    нет")
    print()

    print(f"  [3] КРИТИЧЕСКАЯ МАРЖА  ({len(crit_list)} SKU)  — маржа < 5%")
    print(f"      Действие: поднять цену или снизить себестоимость")
    print("  " + "-" * 114)
    if crit_list:
        for r, profit, margin, cur, need in crit_list:
            name = (r["name"] or "")[:40]
            print(f"    {r['offer_id']:<18} {name:<40} "
                  f"маржа {margin*100:>5.1f}%  цена сейчас {cur:>7,.0f}  "
                  f"→ цель {need:>7,.0f}  приб {money(profit)}")
    else:
        print("    нет")
    print()

    print("=" * 118)
    print(f"  ИТОГО к работе: {len(dead_hot)} карточек + "
          f"{len(star_list)} звёзд + {len(crit_list)} цен")
    print("=" * 118)

    con.close()


if __name__ == "__main__":
    main()
