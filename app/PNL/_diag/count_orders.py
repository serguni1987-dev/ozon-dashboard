import sqlite3

db = r'C:\Users\sergu\Desktop\проект\app\ozon.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

def show(title, q, params=()):
    print(f'\n--- {title} ---')
    try:
        for r in cur.execute(q, params):
            print(r)
    except Exception as e:
        print('ERR:', e)

# 1. realization_daily — заказы за январь
show('realization_daily 2026-01 (все)',
     "SELECT COUNT(DISTINCT posting_number), COUNT(*), SUM(quantity) "
     "FROM realization_daily "
     "WHERE date BETWEEN '2026-01-01' AND '2026-01-31'")

show('realization_daily 2026-01 (без возвратов)',
     "SELECT COUNT(DISTINCT posting_number), COUNT(*), SUM(quantity) "
     "FROM realization_daily "
     "WHERE date BETWEEN '2026-01-01' AND '2026-01-31' AND is_return=0")

# 2. postings_daily — заказы за январь
show('postings_daily 2026-01 (все)',
     "SELECT COUNT(DISTINCT posting_number), COUNT(*), SUM(quantity) "
     "FROM postings_daily "
     "WHERE date BETWEEN '2026-01-01' AND '2026-01-31'")

show('postings_daily 2026-01 (живые)',
     "SELECT COUNT(DISTINCT posting_number), COUNT(*), SUM(quantity) "
     "FROM postings_daily "
     "WHERE date BETWEEN '2026-01-01' AND '2026-01-31' "
     "  AND is_cancelled=0 AND is_returned=0")

# 3. monthly_realization_rows — заказы за январь
show('monthly_realization_rows 2026-01',
     "SELECT COUNT(*), SUM(quantity) FROM monthly_realization_rows "
     "WHERE month='2026-01' AND is_return=0")

# 4. По месяцам из realization_daily
show('realization_daily по месяцам 2026 (distinct posting, без возвратов)',
     "SELECT substr(date,1,7) AS m, "
     "       COUNT(DISTINCT posting_number) AS orders, "
     "       SUM(quantity) AS qty "
     "FROM realization_daily "
     "WHERE date >= '2026-01-01' AND date <= '2026-12-31' AND is_return=0 "
     "GROUP BY m ORDER BY m")

# 5. По месяцам из postings_daily
show('postings_daily по месяцам 2026 (distinct posting)',
     "SELECT substr(date,1,7) AS m, "
     "       COUNT(DISTINCT posting_number) AS orders, "
     "       SUM(quantity) AS qty "
     "FROM postings_daily "
     "WHERE date >= '2026-01-01' AND date <= '2026-12-31' "
     "GROUP BY m ORDER BY m")

conn.close()