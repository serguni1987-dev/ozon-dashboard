import sqlite3
from datetime import datetime, timedelta
from unitka import config
from unitka.ozon_client import OzonClient

def check_db():
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    
    print("=== 1. СОСТОЯНИЕ БАЗЫ ДАННЫХ ===")
    for table in ["realization_daily", "postings_daily", "transactions"]:
        try:
            cur.execute(f"SELECT MAX(date) as max_d, COUNT(*) as cnt FROM {table}")
            row = cur.fetchone()
            print(f"{table:20} | последняя дата: {row['max_d']} | всего строк: {row['cnt']}")
        except Exception as e:
            print(f"{table:20} | ошибка чтения: {e}")
            
    print("\n=== 2. ПОСЛЕДНИЕ ОШИБКИ В LOAD_LOG ===")
    try:
        cur.execute("SELECT date, status, error FROM load_log ORDER BY date DESC LIMIT 5")
        for row in cur.fetchall():
            err = row['error'] if row['error'] else "нет"
            print(f"Дата: {row['date']} | Статус: {row['status']} | Ошибка: {err[:100]}")
    except Exception as e:
        print(f"Ошибка чтения load_log: {e}")
        
    con.close()

def check_api():
    print("\n=== 3. ТЕСТ API OZON (ПРОВЕРКА VPN) ===")
    try:
        config.check_credentials()
        client = OzonClient()
        
        test_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"Отправляем тестовый запрос к Ozon за {test_date}...")
        
        try:
            acc = client.accrual_by_day(test_date)
            print(f"[OK] API Начисления: УСПЕХ. Получено {len(acc.get('accruals', []))} записей.")
        except Exception as e:
            print(f"[ERR] API Начисления: ОШИБКА - {e}")
            
        try:
            payload = {
                "dir": "ASC",
                "filter": {"since": f"{test_date}T00:00:00Z", "to": f"{test_date}T23:59:59Z"},
                "limit": 10,
                "offset": 0
            }
            post = client._post("/v3/posting/fbs/list", payload)
            print(f"[OK] API Отправления: УСПЕХ. Получено {len(post.get('result', {}).get('postings', []))} записей.")
        except Exception as e:
            print(f"[ERR] API Отправления: ОШИБКА - {e}")
            
    except Exception as e:
        print(f"[ERR] КРИТИЧЕСКАЯ ОШИБКА (нет ключей или сети): {e}")

if __name__ == "__main__":
    check_db()
    check_api()