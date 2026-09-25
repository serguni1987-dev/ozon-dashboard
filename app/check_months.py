import sqlite3
c = sqlite3.connect("ozon.db")

print("=== accruals по месяцам ===")
for m, n in c.execute("SELECT substr(date,1,7) AS m, COUNT(*) FROM accruals GROUP BY m ORDER BY m"):
    print(f"  {m}  {n:>5}")

print()
print("=== accruals_services по месяцам ===")
for m, n in c.execute("SELECT substr(date,1,7) AS m, COUNT(*) FROM accruals_services GROUP BY m ORDER BY m"):
    print(f"  {m}  {n:>5}")

print()
print("=== monthly_realization_rows по месяцам ===")
for m, n in c.execute("SELECT month, COUNT(*) FROM monthly_realization_rows GROUP BY month ORDER BY month"):
    print(f"  {m}  {n:>5}")