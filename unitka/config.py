r"""Конфиг unitka — единственное место, где заданы пути, ID таблицы и ключи.

Порядок поиска значения: переменная окружения → проект\.env → проект\app\.env → значение по умолчанию.
Параметры установки: PULT_HOME (папка проекта, только переменная окружения), PULT_SHEET_ID,
PULT_COSTS_CSV, PULT_AI_MODEL, OZON_CLIENT_ID, OZON_API_KEY.
"""
import os
from pathlib import Path

# Папка проекта = папка, в которой лежит unitka (раньше был зашит путь C:\Users\sergu\Desktop\проект).
# Переопределить можно переменной окружения PULT_HOME — нужно для установки у других продавцов.
PROJECT = Path(os.environ.get("PULT_HOME") or Path(__file__).resolve().parent.parent)
APP     = PROJECT / "app"
DB_PATH = APP / "ozon.db"
LOGS    = PROJECT / "_logs"

CREDENTIALS = APP / "credentials.json"
MARGIN_SHEET = "Юнит экономика"
SETTINGS_SHEET = "НАСТРОЙКИ"

# Таблица владельца проекта. Оставлена как запасное значение, чтобы текущая установка
# не сломалась; у нового продавца ID таблицы пишет install.ps1 в app\.env (PULT_SHEET_ID).
_LEGACY_SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"


def _load_env() -> dict:
    """Читает .env из проект\\ и проект\\app\\. Снимает BOM, если он есть."""
    out = {}
    for p in (PROJECT / ".env", APP / ".env"):
        if not p.exists():
            continue
        # utf-8-sig: если BOM есть — срежет, если нет — обычный utf-8
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        for line in text.splitlines():
            line = line.lstrip("\ufeff").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().lstrip("\ufeff")
            v = v.strip().strip('"').strip("'").lstrip("\ufeff")
            if k:
                out[k] = v
    return out


_env = _load_env()


def _pick(*names: str) -> str:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    for n in names:
        v = _env.get(n)
        if v:
            return v.strip()
    return ""


OZON_CLIENT_ID = _pick("OZON_CLIENT_ID", "OZON_CLIENT", "CLIENT_ID")
OZON_API_KEY   = _pick("OZON_API_KEY",   "OZON_KEY",    "API_KEY")
OZON_BASE_URL  = _pick("OZON_BASE_URL") or "https://api-seller.ozon.ru"

# --- Настройки установки: переменная окружения → app\.env → значение по умолчанию ---
SHEET_ID  = _pick("PULT_SHEET_ID") or _LEGACY_SHEET_ID                       # ID Google-таблицы
COSTS_CSV = Path(_pick("PULT_COSTS_CSV") or PROJECT / "costs_all.csv")        # себестоимость
AI_MODEL  = _pick("PULT_AI_MODEL") or "qwen2.5:3b-instruct"                   # модель Ollama


def check_credentials() -> None:
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        raise SystemExit(
            "Не найдены OZON_CLIENT_ID / OZON_API_KEY.\n"
            f"Искали в env и в {PROJECT / '.env'} / {APP / '.env'}\n"
            f"CLIENT_ID={'да' if OZON_CLIENT_ID else 'нет'}, "
            f"API_KEY={'да' if OZON_API_KEY else 'нет'}"
        )
