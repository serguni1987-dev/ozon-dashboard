"""Сводка по realization_daily за месяц."""
import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\sergu\Desktop\проект\app\ozon.db")


def main():
    if len(sys.argv) < 2:
        print("Укажи месяц: py -m unitka._diag.check_month 2026-08")
        return
    month = sys.argv[1]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    print(f"=== realization_daily, {month} ===")
    r = con.execute("""
        SELECT COUNT(*) AS n, SUM(quantity) AS qty,
               ROUND(SUM(seller_price),2) AS seller,
               ROUND(SUM(sale_price),2)   AS sale,
               ROUND(SUM(bonus),2)        AS bonus,
               ROUND(SUM(coinvestment),2) AS coinv,
               ROUND(SUM(commission),2)   AS comm,
               ROUND(SUM(delivery_total),2) AS dl
        FROM realization_daily WHERE substr(date,1,7)=?
    """, (month,)).fetchone()
    print(f"  строк:          {r['n']}")
    print(f"  quantity:       {r['qty']}")
    print(f"  seller_price:   {r['seller']}")
    print(f"  sale_price:     {r['sale']}")
    print(f"  bonus:          {r['bonus']}")
    print(f"  coinvestment:   {r['coinv']}")
    print(f"  commission:     {r['comm']}")
    print(f"  delivery_total: {r['dl']}")
    print()

    print(f"=== accrual_sku_daily, {month} ===")
    for row in con.execute("""
        SELECT a.type_id, t.name, COUNT(*) AS n, ROUND(SUM(a.amount),2) AS total
        FROM accrual_sku_daily a
        LEFT JOIN accrual_types t ON t.id = a.type_id
        WHERE substr(a.date,1,7)=?
        GROUP BY a.type_id ORDER BY a.type_id
    """, (month,)):
        nm = row["name"] or "?"
        print(f"  {row['type_id']:>4}  {nm:<40}  n={row['n']:>4}  total={row['total']:>12.2f}")
    print()

    print(f"=== accrual_non_item_daily, {month} ===")
    for row in con.execute("""
        SELECT a.kind, a.type_id, t.name, COUNT(*) AS n, ROUND(SUM(a.amount),2) AS total
        FROM accrual_non_item_daily a
        LEFT JOIN accrual_types t ON t.id = a.type_id
        WHERE substr(a.date,1,7)=?
        GROUP BY a.kind, a.type_id ORDER BY a.kind, a.type_id
    """, (month,)):
        nm = row["name"] or "?"
        print(f"  {row['kind']:<10} {row['type_id']:>4}  {nm:<30}  n={row['n']:>3}  total={row['total']:>12.2f}")
    print()

    print(f"=== monthly_realization_rows за {month} ===")
    m = con.execute("""
        SELECT COUNT(*) AS n, SUM(quantity) AS qty,
               ROUND(SUM(seller_price),2) AS seller,
               ROUND(SUM(sale_price),2)   AS sale,
               ROUND(SUM(bonus),2)        AS bonus,
               ROUND(SUM(coinvestment),2) AS coinv,
               ROUND(SUM(gross_commission),2) AS comm
        FROM monthly_realization_rows
        WHERE month=? AND is_return=0
    """, (month,)).fetchone()
    if m["n"]:
        print(f"  строк:          {m['n']}")
        print(f"  quantity:       {m['qty']}")
        print(f"  seller_price:   {m['seller']}")
        print(f"  sale_price:     {m['sale']}")
        print(f"  bonus:          {m['bonus']}")
        print(f"  coinvestment:   {m['coinv']}")
        print(f"  commission:     {m['comm']}")
    else:
        print("  (нет данных)")

    con.close()


if __name__ == "__main__":
    main()
