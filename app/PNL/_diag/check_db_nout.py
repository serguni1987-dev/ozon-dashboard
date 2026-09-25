import sqlite3
c = sqlite3.connect("ozon.db")

n = c.execute("SELECT COUNT(*) FROM accruals_services").fetchone()[0]
print(f"accruals_services: {n}")

idx = c.execute("""
    SELECT name FROM sqlite_master
    WHERE type='index' AND name='idx_accruals_services_unique'
""").fetchone()
print(f"UNIQUE INDEX: {idx}")

dups = c.execute("""
    SELECT COUNT(*) FROM (
        SELECT 1 FROM accruals_services
        GROUP BY accrual_id, type_id, date, amount
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]
print(f"Групп с дублями: {dups}")