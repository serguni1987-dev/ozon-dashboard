"""
diagnose.py
Диагностика данных в ozon.db — проверяем гипотезы.
"""
import sqlite3
import os

DB_PATH = "ozon.db"


def q(conn, title, sql):
    print("=" * 70)
    print(title)
    print("=" * 70)
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        print("(пусто)\n")
        return
    widths = [max(len(str(c)), max(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)]
    print(" | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols)))
    print("-" * 70)
    for r in rows:
        print(" | ".join(str(v if v is not None else '—').ljust(widths[i]) for i, v in enumerate(r)))
    print(f"({len(rows)} строк)\n")


def main():
    conn = sqlite3.connect(DB_PATH)

    # 1. ДРР — реально ли везде 0?
    q(conn, "1. Распределение ДРР", """
        SELECT
            CASE
                WHEN drr IS NULL THEN 'NULL'
                WHEN drr = 0 THEN '0%'
                WHEN drr < 0.05 THEN '0-5%'
                WHEN drr < 0.15 THEN '5-15%'
                WHEN drr < 0.30 THEN '15-30%'
                ELSE '30%+'
            END AS bucket,
            COUNT(*) AS rows_cnt,
            COUNT(DISTINCT sku) AS sku_cnt
        FROM sales_daily
        GROUP BY bucket
        ORDER BY rows_cnt DESC
    """)

    # 2. Бренды в отчёте
    q(conn, "2. Бренды (топ-10)", """
        SELECT
            p.brand,
            COUNT(DISTINCT s.sku)         AS sku_count,
            ROUND(SUM(s.revenue), 0)      AS revenue
        FROM sales_daily s
        JOIN products p ON p.sku = s.sku
        GROUP BY p.brand
        ORDER BY revenue DESC
        LIMIT 10
    """)

    # 3. ABC-анализ: сколько SKU дают 80% выручки
    print("=" * 70)
    print("3. ABC-анализ (сколько SKU дают X% выручки)")
    print("=" * 70)
    cur = conn.execute("""
        SELECT sku, SUM(revenue) AS rev
        FROM sales_daily
        GROUP BY sku
        HAVING rev > 0
        ORDER BY rev DESC
    """)
    rows = cur.fetchall()
    if rows:
        total = sum(r[1] for r in rows)
        cumulative = 0
        for i, (sku, rev) in enumerate(rows, 1):
            cumulative += rev
            pct = cumulative / total * 100
            if pct >= 80:
                print(f"  80% выручки делают {i} SKU (из {len(rows)} продающих)")
                break
        cumulative = 0
        for i, (sku, rev) in enumerate(rows, 1):
            cumulative += rev
            pct = cumulative / total * 100
            if pct >= 95:
                print(f"  95% выручки делают {i} SKU")
                break
        print(f"  Всего продающих SKU: {len(rows)}")
        print(f"  Общая выручка: {total:.0f} ₽")
    print()

    # 4. SKU без продаж, но с показами
    q(conn, "4. SKU без продаж, но с показами (топ-10)", """
        SELECT
            p.offer_id,
            SUBSTR(p.name, 1, 35)         AS name,
            SUM(s.views_total)            AS views,
            SUM(s.orders_units)           AS orders
        FROM sales_daily s
        JOIN products p ON p.sku = s.sku
        GROUP BY s.sku
        HAVING orders = 0 AND views > 0
        ORDER BY views DESC
        LIMIT 10
    """)

    # 5. SKU, у которых за период было >5 показов, но < 1 заказа
    q(conn, "5. Мёртвые SKU (показы есть, заказов 0)", """
        SELECT COUNT(DISTINCT sku) AS dead_sku_count,
               SUM(views_total) AS total_wasted_views
        FROM sales_daily
        WHERE sku IN (
            SELECT sku FROM sales_daily
            GROUP BY sku
            HAVING SUM(orders_units) = 0 AND SUM(views_total) > 100
        )
    """)

    # 6. Проверка пустых полей
    q(conn, "6. Заполненность полей", """
        SELECT
            'revenue'         AS field, COUNT(*) - COUNT(revenue)         AS nulls FROM sales_daily
        UNION ALL SELECT 'drr',            COUNT(*) - COUNT(drr)           FROM sales_daily
        UNION ALL SELECT 'stock',          COUNT(*) - COUNT(stock)         FROM sales_daily
        UNION ALL SELECT 'position_search',COUNT(*) - COUNT(position_search) FROM sales_daily
        UNION ALL SELECT 'rating',         COUNT(*) - COUNT(rating)        FROM sales_daily
        UNION ALL SELECT 'reviews',        COUNT(*) - COUNT(reviews)       FROM sales_daily
        UNION ALL SELECT 'price_index',    COUNT(*) - COUNT(price_index)   FROM sales_daily
    """)

    conn.close()


if __name__ == "__main__":
    main()