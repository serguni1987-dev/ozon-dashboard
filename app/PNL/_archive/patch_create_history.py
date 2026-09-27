"""patch_create_history.py — правит пути в create_cost_history.py."""

path = "Себестоимость/create_cost_history.py"
src = open(path, encoding="utf-8").read()

OLD = '''import sqlite3

DB = "ozon.db"'''

NEW = '''import sqlite3
import os

COST_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(COST_DIR)
DB = os.path.join(APP_DIR, "ozon.db")'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    open(path, "w", encoding="utf-8").write(src)
    print("[OK] create_cost_history.py пропатчен")
elif "COST_DIR" in src:
    print("[i] Уже пропатчен")
else:
    print("[?] Не нашёл блок. Покажи первые 10 строк вручную")