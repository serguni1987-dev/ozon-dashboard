import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row

print("Всего в postings_daily:")
for r in con.execute("SELECT COUNT(*) AS n FROM postings_daily"):
    print("  строк:", r["n"])

print("\nПо источникам за 01.09-03.10:")
for r in con.execute("""
    SELECT source, COUNT(*) AS n, SUM(quantity) AS qty,
           SUM(is_cancelled) AS canc, SUM(is_returned) AS ret
    FROM postings_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-10-03'
    GROUP BY source
"""):
    print(f"  {r['source']}: строк={r['n']}, qty={r['qty']}, "
          f"отмен={r['canc']}, возвратов={r['ret']}")

print("\nВсе статусы за период (source=xlsx_report):")
for r in con.execute("""
    SELECT status, COUNT(*) AS n, SUM(quantity) AS qty
    FROM postings_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-10-03'
      AND source='xlsx_report'
    GROUP BY status
    ORDER BY n DESC
"""):
    print(f"  {r['status']!r}: {r['n']} строк, qty={r['qty']}")

print("\nДиапазон дат:")
for r in con.execute("""
    SELECT MIN(date) AS mn, MAX(date) AS mx
    FROM postings_daily
    WHERE source='xlsx_report'
"""):
    print(f"  {r['mn']} .. {r['mx']}")