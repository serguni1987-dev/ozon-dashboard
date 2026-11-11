"""unitka/doctor.py — самопроверка установки. Ничего не меняет: только читает и печатает.

    py -m unitka.doctor             полная проверка (нужны интернет и VPN)
    py -m unitka.doctor --offline   без обращений к Ozon, Google и Ollama

Код возврата 0 — всё обязательное в порядке, 1 — есть ошибки. Значения ключей не печатаются.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from . import config

REQUIRED_PACKAGES = [
    ("gspread", "gspread"), ("google.oauth2.service_account", "google-auth"),
    ("dotenv", "python-dotenv"), ("requests", "requests"), ("pandas", "pandas"),
    ("openpyxl", "openpyxl"), ("dateutil", "python-dateutil"),
]
REQUIRED_SHEETS = ["НАСТРОЙКИ"]

_errors = 0


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[--] {msg}")


def fail(msg: str) -> None:
    global _errors
    _errors += 1
    print(f"[!!] {msg}")


def check_python() -> None:
    v = sys.version_info
    (ok if v >= (3, 11) else fail)(f"Python {v.major}.{v.minor}.{v.micro} (нужен 3.11 или новее)")
    for module, package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(module)
        except Exception:  # noqa: BLE001
            fail(f"нет пакета {package}: py -m pip install -r requirements.txt")


def check_files() -> dict:
    ok(f"папка проекта: {config.PROJECT}")
    if not (config.APP / ".env").exists() and not (config.PROJECT / ".env").exists():
        fail(f"нет файла {config.APP / '.env'} — запустите install.ps1")
    (ok if config.OZON_CLIENT_ID else fail)("OZON_CLIENT_ID " + ("задан" if config.OZON_CLIENT_ID else "не задан"))
    (ok if config.OZON_API_KEY else fail)("OZON_API_KEY " + ("задан" if config.OZON_API_KEY else "не задан"))
    if config.SHEET_ID == getattr(config, "_LEGACY_SHEET_ID", None) and not config._pick("PULT_SHEET_ID"):
        warn("PULT_SHEET_ID не задан в app\\.env — используется таблица по умолчанию из config.py")
    else:
        ok("PULT_SHEET_ID задан")
    info = {}
    if config.CREDENTIALS.exists():
        try:
            info = json.loads(config.CREDENTIALS.read_text(encoding="utf-8-sig"))
            ok(f"ключ Google: {info.get('client_email', '?')} — этому адресу нужен доступ «Редактор» к таблице")
        except Exception as exc:  # noqa: BLE001
            fail(f"credentials.json не читается: {exc}")
    else:
        fail(f"нет файла {config.CREDENTIALS} (ключ сервисного аккаунта Google)")
    (ok if config.COSTS_CSV.exists() else warn)(
        f"себестоимость: {config.COSTS_CSV}" + ("" if config.COSTS_CSV.exists() else " — файла нет, прибыль не посчитается"))
    return info


def check_db() -> None:
    from . import init_db
    if not config.DB_PATH.exists():
        fail(f"нет базы {config.DB_PATH}: py -m unitka.init_db")
        return
    m = init_db.missing()
    if m:
        fail("в базе не хватает таблиц: " + ", ".join(m) + " → py -m unitka.init_db")
    else:
        ok(f"база {config.DB_PATH.name}: все таблицы на месте")


def check_ozon() -> None:
    if not (config.OZON_CLIENT_ID and config.OZON_API_KEY):
        return
    try:
        from .ozon_client import OzonClient
        data = OzonClient()._post("/v5/product/info/prices",
                                  {"cursor": "", "filter": {"visibility": "ALL"}, "limit": 1})
        ok(f"Ozon API отвечает (товаров в кабинете: {data.get('total', '?')})")
    except Exception as exc:  # noqa: BLE001
        fail(f"Ozon API: {str(exc)[:200]}")


def check_sheets() -> None:
    if not config.CREDENTIALS.exists():
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            str(config.CREDENTIALS), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)
        titles = {ws.title for ws in sh.worksheets()}
        ok(f"таблица открыта: «{sh.title}», листов {len(titles)}")
        for name in REQUIRED_SHEETS:
            (ok if name in titles else fail)(f"лист «{name}» " + ("есть" if name in titles else "не найден"))
    except Exception as exc:  # noqa: BLE001
        fail(f"Google Sheets: {type(exc).__name__}: {str(exc)[:200]} (VPN включён? таблица открыта для сервисного аккаунта?)")


def check_ollama() -> None:
    """Локальная ИИ необязательна: без неё сводка выходит по шаблону."""
    import os
    try:
        import requests
        host = (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        if not host.startswith("http"):
            host = "http://" + host
        names = [m.get("name", "") for m in requests.get(f"{host}/api/tags", timeout=5).json().get("models", [])]
    except Exception:  # noqa: BLE001
        warn("Ollama не запущена — режим «наставник» будет по шаблону (установка: install.ps1 -WithAI)")
        return
    if config.AI_MODEL in names:
        ok(f"Ollama: модель {config.AI_MODEL} установлена")
    else:
        warn(f"Ollama работает, но модели {config.AI_MODEL} нет: ollama pull {config.AI_MODEL}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Самопроверка установки Пульта")
    ap.add_argument("--offline", action="store_true", help="не обращаться к Ozon, Google и Ollama")
    args = ap.parse_args()
    print("=== Проверка установки «Пульт Ozon» ===")
    check_python()
    check_files()
    check_db()
    if not args.offline:
        check_ozon()
        check_sheets()
        check_ollama()
    print("=== Итог: " + ("всё в порядке ===" if not _errors else f"ошибок: {_errors} ==="))
    sys.exit(1 if _errors else 0)


if __name__ == "__main__":
    main()
