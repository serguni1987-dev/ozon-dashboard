import os, sys, time, requests, sqlite3
from dotenv import load_dotenv

load_dotenv(r'C:\Users\sergu\Desktop\проект\app\.env')
H = {
    'Client-Id': os.getenv('OZON_CLIENT_ID'),
    'Api-Key':   os.getenv('OZON_API_KEY'),
    'Content-Type': 'application/json',
}
if not H['Client-Id'] or not H['Api-Key']:
    print('Нет кредов в .env — проверь OZON_CLIENT_ID / OZON_API_KEY')
    sys.exit(1)

db = r'C:\Users\sergu\Desktop\проект\app\ozon.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS orders_created (
  posting_number TEXT,
  created_at     TEXT,
  scheme         TEXT,
  status         TEXT,
  PRIMARY KEY(posting_number, scheme)
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders_created(created_at)")
conn.commit()

def month_range(year, month):
    d1 = f'{year}-{month:02d}-01T00:00:00Z'
    if month == 12:
        d2 = f'{year+1}-01-01T00:00:00Z'
    else:
        d2 = f'{year}-{month+1:02d}-01T00:00:00Z'
    return d1, d2

def _extract(data):
    # FBS v3: {'result': {'postings': [...]}}
    # FBO v2: {'result': [...]}
    # и на всякий случай — если вдруг list напрямую
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    result = data.get('result', [])
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get('postings', []) or result.get('items', [])
    return []


def fetch(endpoint, since, to):
    out, offset = [], 0
    while True:
        body = {
            'dir': 'ASC',
            'filter': {'since': since, 'to': to},
            'limit': 1000,
            'offset': offset,
        }
        try:
            r = requests.post(f'https://api-seller.ozon.ru{endpoint}',
                              headers=H, json=body, timeout=60)
            r.raise_for_status()
        except Exception as e:
            print(' ERR', endpoint, since[:7], e)
            return out
        posts = _extract(r.json())
        if not posts:
            break
        out.extend(posts)
        offset += 1000
        if len(posts) < 1000:
            break
    return out
for m in range(1, 11):
    since, to = month_range(2026, m)
    for scheme, ep in [('FBS', '/v3/posting/fbs/list'),
                       ('FBO', '/v2/posting/fbo/list')]:
        posts = fetch(ep, since, to)
        for p in posts:
            cur.execute(
                "INSERT OR REPLACE INTO orders_created VALUES (?,?,?,?)",
                (p.get('posting_number'),
                 p.get('created_at') or p.get('in_process_at'),
                 scheme,
                 p.get('status', ''))
            )
        print(f'{since[:7]} {scheme}: {len(posts)}')
        time.sleep(0.3)
    conn.commit()

print('\n--- orders_created по месяцам ---')
for r in cur.execute("""
    SELECT substr(created_at, 1, 7) AS m, COUNT(*) AS c
    FROM orders_created WHERE created_at IS NOT NULL
    GROUP BY m ORDER BY m
"""):
    print(r)

conn.close()