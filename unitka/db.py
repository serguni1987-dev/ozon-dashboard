import sqlite3
import os

# База лежит в папке app, на уровень ниже unitka
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
DB_PATH = os.path.join(APP_DIR, "ozon.db")

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema(con=None):
    """Заглушка: схема БД уже создана. Оставлено для совместимости со старыми модулями."""
    pass