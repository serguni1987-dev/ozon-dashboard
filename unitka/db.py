import sqlite3
import os

# Путь к базе — из config (папка проекта или переменная PULT_HOME), чтобы db и config
# не могли разойтись при установке на другом компьютере.
from .config import APP as _APP, DB_PATH as _DB_PATH

APP_DIR = str(_APP)
DB_PATH = str(_DB_PATH)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema(con=None):
    """Создаёт недостающие таблицы по unitka/schema.sql (CREATE IF NOT EXISTS).
    Существующие таблицы и данные не меняются; никогда не падает. Раньше здесь была заглушка."""
    try:
        from .init_db import ensure
        own = con is None
        con = con or sqlite3.connect(DB_PATH)
        ensure(con)
        if own:
            con.close()
    except Exception as exc:  # noqa: BLE001 — загрузчики не должны падать из-за схемы
        print(f"[db] схема не проверена: {exc}")
