"""Показать содержимое realization_daily за дату.

    py -m unitka._diag.check_day 2026-08-15
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\sergu\Desktop\проект\app\ozon.db")


def main():
    if len(sys.argv) < 2:
        print("Укажи дату: py -m unitka._diag.check_day 2026-08-15")
        return
    day = sys.argv[1]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT sku, quantity, seller_price, sale_price, bonus,
               coinvestment, commission, commission_ratio, delivery_total
        FROM realization_daily
        WHERE date = ?
        ORDER BY sku
    """, (day,)).fetchall()

    print(f"realization_daily за {day}: {len(rows)} строк")
    for r in rows:
        print(
            f"  sku={r['sku']}  qty={r['quantity']}  "
            f"seller_price={r['seller_price']:.2f}  sale_price={r['sale_price']:.2f}  "
            f"bonus={r['bonus']:.2f}  coinv={r['coinvestment']:.2f}  "
            f"comm={r['commission']:.2f}  ratio={r['commission_ratio']:.4f}  "
            f"delivery={r['delivery_total']:.2f}"
        )

    # Итоги
    tot = con.execute("""
        SELECT COUNT(*) AS n,
               SUM(seller_price) AS seller,
               SUM(sale_price) AS sale,
               SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv,
               SUM(commission) AS comm,
               SUM(delivery_total) AS dl
        FROM realization_daily WHERE date = ?
    """, (day,)).fetchone()
    print()
    print(f"ИТОГО за {day}:")
    print(f"  seller_price  = {tot['seller']:.2f}")
    print(f"  sale_price    = {tot['sale']:.2f}")
    print(f"  bonus         = {tot['bonus']:.2f}")
    print(f"  coinvestment  = {tot['coinv']:.2f}")
    print(f"  commission    = {tot['comm']:.2f}")
    print(f"  delivery      = {tot['dl']:.2f}")

    # Услуги по SKU
    sku_fees = con.execute("""
        SELECT type_id, COUNT(*) AS n, SUM(amount) AS total
        FROM accrual_sku_daily WHERE date = ?
        GROUP BY type_id ORDER BY type_id
    """, (day,)).fetchall()
    print()
    print(f"accrual_sku_daily за {day}: {len(sku_fees)} типов")
    for r in sku_fees:
        print(f"  type_id={r['type_id']:>3}  n={r['n']:>3}  total={r['total']:.2f}")

    non_item = con.execute("""
        SELECT kind, type_id, COUNT(*) AS n, SUM(amount) AS total
        FROM accrual_non_item_daily WHERE date = ?
        GROUP BY kind, type_id ORDER BY kind, type_id
    """, (day,)).fetchall()
    print()
    print(f"accrual_non_item_daily за {day}: {len(non_item)} записей")
    for r in non_item:
        print(f"  kind={r['kind']}  type_id={r['type_id']}  n={r['n']}  total={r['total']:.2f}")

    con.close()


if __name__ == "__main__":
    main()
