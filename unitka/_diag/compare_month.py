"""Сравнить monthly_realization_rows с realization_daily за месяц по SKU."""
import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\sergu\Desktop\проект\app\ozon.db")


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # monthly
    monthly = {}
    for r in con.execute("""
        SELECT sku, SUM(seller_price) AS sp, SUM(CASE WHEN seller_price > 0 THEN quantity ELSE 0 END) - SUM(CASE WHEN seller_price < 0 THEN quantity ELSE 0 END) AS q
        FROM monthly_realization_rows
        WHERE month=? AND is_return=0
        GROUP BY sku
    """, (month,)):
        monthly[r["sku"]] = (round(r["sp"] or 0, 2), r["q"] or 0)

    # daily
    daily = {}
    for r in con.execute("""
        SELECT sku, SUM(seller_price) AS sp, SUM(CASE WHEN seller_price > 0 THEN quantity ELSE 0 END) - SUM(CASE WHEN seller_price < 0 THEN quantity ELSE 0 END) AS q
        FROM realization_daily
        WHERE substr(date,1,7)=? AND (seller_price != 0 OR commission != 0)
        GROUP BY sku
    """, (month,)):
        daily[r["sku"]] = (round(r["sp"] or 0, 2), r["q"] or 0)

    all_skus = sorted(set(monthly) | set(daily))
    print(f"{'sku':>12}  {'monthly ₽':>12} {'q':>3}  {'daily ₽':>12} {'q':>3}  Δ₽")
    for sku in all_skus:
        m = monthly.get(sku, (0, 0))
        d = daily.get(sku, (0, 0))
        delta = d[0] - m[0]
        marker = "  <<<" if abs(delta) > 0.01 or m[1] != d[1] else ""
        print(f"{sku:>12}  {m[0]:>12.2f} {m[1]:>3}  {d[0]:>12.2f} {d[1]:>3}  {delta:+10.2f}{marker}")

    print()
    sm = sum(v[0] for v in monthly.values())
    sd = sum(v[0] for v in daily.values())
    qm = sum(v[1] for v in monthly.values())
    qd = sum(v[1] for v in daily.values())
    print(f"ИТОГО monthly: {sm:.2f} q={qm}")
    print(f"ИТОГО daily:   {sd:.2f} q={qd}")
    print(f"РАЗНИЦА:       {sd - sm:+.2f} q={qd - qm:+d}")

    con.close()


if __name__ == "__main__":
    main()
