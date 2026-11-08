r"""Конфиг unitka. Ключи Ozon из app\.env (или из переменных окружения)."""
import os
from pathlib import Path

PROJECT = Path(r"C:\Users\sergu\Desktop\проект")
APP     = PROJECT / "app"
DB_PATH = APP / "ozon.db"

CREDENTIALS = APP / "credentials.json"
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
MARGIN_SHEET = "Юнит экономика"
SETTINGS_SHEET = "НАСТРОЙКИ"


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


def check_credentials() -> None:
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        raise SystemExit(
            "Не найдены OZON_CLIENT_ID / OZON_API_KEY.\n"
            f"Искали в env и в {PROJECT / '.env'} / {APP / '.env'}\n"
            f"CLIENT_ID={'да' if OZON_CLIENT_ID else 'нет'}, "
            f"API_KEY={'да' if OZON_API_KEY else 'нет'}"
        )
