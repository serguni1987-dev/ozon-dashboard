import sqlite3
con = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
con.row_factory = sqlite3.Row
print("=== За 01.09-04.10 по источникам ===")
for r in con.execute("""
    SELECT source, COUNT(*) AS n, SUM(quantity) AS qty,
           SUM(is_cancelled) AS canc, SUM(is_returned) AS ret
    FROM postings_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-10-04'
    GROUP BY source ORDER BY source
"""):
    print(f"  {r['source']}: n={r['n']}, qty={r['qty']}, "
          f"отмен={r['canc']}, возвратов={r['ret']}")

print("\n=== ИТОГО за 01.09-04.10 ===")
for r in con.execute("""
    SELECT COUNT(*) AS n, SUM(quantity) AS qty,
           SUM(is_cancelled) AS canc, SUM(is_returned) AS ret
    FROM postings_daily
    WHERE date BETWEEN '2026-09-01' AND '2026-10-04'
"""):
    print(f"  Заказы: {r['qty']}")
    print(f"  Отмены: {r['canc']}")
    print(f"  Возвраты: {r['ret']}")
    print(f"  Выкупы: {r['qty'] - r['canc'] - r['ret']}")

print("\n=== Эталон ===")
print("  Заказы: 64, Отмены: 38, Возвраты: 1, Выкупы: 21")