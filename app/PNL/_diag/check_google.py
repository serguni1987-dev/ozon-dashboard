import requests
try:
    r = requests.get("https://www.googleapis.com", timeout=10)
    print(f"Google API: {r.status_code}")
except Exception as e:
    print(f"Ошибка: {e}")
