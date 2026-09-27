src = open("sync_monthly.py", encoding="utf-8").read()

old = '''load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v2/finance/realization"
DB = "ozon.db"'''

new = '''APP_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(APP_DIR, ".env")
DB = os.path.join(APP_DIR, "ozon.db")

load_dotenv(ENV_PATH)

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v2/finance/realization"'''

if old in src:
    src = src.replace(old, new)
    open("sync_monthly.py", "w", encoding="utf-8").write(src)
    print("[OK] Патч применён")
else:
    print("[i] Блок не найден — уже пропатчен или отличается")
