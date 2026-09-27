"""
query.py
Быстрые SQL-запросы к ozon.db для проверки данных.
Запуск: py query.py
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "ozon.db"


def q(conn, title, sql, params=()):
    print("=" * 70)
    print(title)
    print("=" * 70)
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("(пусто)")
        print()
        return
    # Ширина колонок
    widths = [max(len(str(c)), max(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    print(" | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols)))
    print("-" * 70)
    for r in rows:
        print(" | ".join(str(v if v is not None else '—').ljust(widths[i]) for i, v in enumerate(r)))
    print(f"({len(rows)} строк)")
    print()


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] {DB_PATH} не найден")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. Общая сводка за период
                # 1. Общая сводка за период (только свои SKU)
        q(conn, "1. Сводка (свои SKU)", """
            SELECT
                COUNT(DISTINCT s.sku)           AS sku_count,
                COUNT(*)                        AS rows_count,
                MIN(s.date)                     AS date_from,
                MAX(s.date)                     AS date_to,
                ROUND(SUM(s.revenue), 2)        AS revenue_total,
                SUM(s.orders_units)             AS orders_total,
                SUM(s.views_total)              AS views_total,
                SUM(s.cart_adds_total)          AS cart_adds_total
            FROM sales_daily s
            JOIN products p ON p.sku = s.sku
            WHERE p.is_own = 1
        """)

        # 2. Топ-10 SKU по выручке за весь период
        q(conn, "2. Топ-10 SKU по выручке (за весь период)", """
            SELECT
                p.offer_id,
                p.sku,
                SUBSTR(p.name, 1, 40)            AS name,
                ROUND(SUM(s.revenue), 0)         AS revenue,
                SUM(s.orders_units)              AS orders,
                SUM(s.views_total)               AS views,
                ROUND(AVG(s.drr) * 100, 2)       AS avg_drr_pct
            FROM sales_daily s
            JOIN products p ON p.sku = s.sku
            GROUP BY s.sku
            ORDER BY revenue DESC
            LIMIT 10
        """)

        # 3. Динамика по дням (для дашборда)
        q(conn, "3. Динамика по дням", """
            SELECT
                date,
                ROUND(SUM(revenue), 0)      AS revenue,
                SUM(orders_units)           AS orders,
                SUM(views_total)            AS views,
                ROUND(SUM(cart_adds_total)*100.0 / NULLIF(SUM(views_total),0), 2) AS cr_pct
            FROM sales_daily
            GROUP BY date
            ORDER BY date
        """)

        # 4. SKU с высоким ДРР (риск убытка)
        q(conn, "4. SKU с ДРР > 15% и выручкой > 5000 ₽", """
            SELECT
                p.offer_id,
                SUBSTR(p.name, 1, 35)        AS name,
                ROUND(SUM(s.revenue), 0)     AS revenue,
                ROUND(AVG(s.drr) * 100, 2)   AS avg_drr_pct,
                SUM(s.orders_units)          AS orders
            FROM sales_daily s
            JOIN products p ON p.sku = s.sku
            GROUP BY s.sku
            HAVING avg_drr_pct > 15 AND revenue > 5000
            ORDER BY avg_drr_pct DESC
            LIMIT 10
        """)

        # 5. SKU с остатком < 5, но продажами
        q(conn, "5. SKU с остатком < 5 шт (риск out-of-stock)", """
            SELECT
                p.offer_id,
                SUBSTR(p.name, 1, 35)        AS name,
                MAX(s.stock)                 AS stock_last,
                SUM(s.orders_units)          AS orders_period,
                ROUND(SUM(s.revenue), 0)     AS revenue
            FROM sales_daily s
            JOIN products p ON p.sku = s.sku
            WHERE s.date = (SELECT MAX(date) FROM sales_daily)
              AND s.stock IS NOT NULL
              AND s.stock < 5
              AND s.stock > 0
            GROUP BY s.sku
            ORDER BY orders_period DESC
            LIMIT 10
        """)

                # 6. Топ категорий (только свои SKU)
        q(conn, "6. Топ-10 категорий по выручке (свои SKU)", """
            SELECT
                p.category_l2,
                COUNT(DISTINCT s.sku)         AS sku_count,
                ROUND(SUM(s.revenue), 0)      AS revenue,
                SUM(s.orders_units)           AS orders
            FROM sales_daily s
            JOIN products p ON p.sku = s.sku
            WHERE p.is_own = 1
            GROUP BY p.category_l2
            ORDER BY revenue DESC
            LIMIT 10
        """)

    finally:
        conn.close()


if __name__ == "__main__":
    main()