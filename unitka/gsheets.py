"""unitka/gsheets.py — доступ к Google Sheets для аналитических листов.

Не зависит от конкретных имён констант в unitka/config.py:
ищет креды по цепочке env -> config -> стандартные имена файлов.

Использование:
    from unitka import gsheets
    ws = gsheets.open_ws("Воронка")                    # создаст лист, если нет
    ws = gsheets.open_ws("НАСТРОЙКИ", create=False)    # только если существует
    val = gsheets.read_cell(ws, "B1")
    gsheets.write_table(ws, header, rows)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
from .config import SHEET_ID as DEFAULT_SPREADSHEET_ID  # app\.env → PULT_SHEET_ID
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_client: gspread.Client | None = None


def _config_attr(names: tuple[str, ...]):
    """Ищет первую непустую константу из names в unitka.config."""
    try:
        from unitka import config as cfg  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    for name in names:
        value = getattr(cfg, name, None)
        if value:
            return value
    return None


def _creds_path() -> Path:
    env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env and Path(env).exists():
        return Path(env)

    value = _config_attr((
        "GOOGLE_CREDS_FILE", "CREDS_FILE", "SERVICE_ACCOUNT_FILE",
        "GCP_CREDS_FILE", "GOOGLE_JSON", "CREDENTIALS_FILE",
    ))
    if value and Path(str(value)).exists():
        return Path(str(value))

    for candidate in (
        "credentials.json", "creds.json", "service_account.json", "google_creds.json",
        "app/credentials.json", "app/creds.json", "_secrets/credentials.json",
    ):
        path = PROJECT_ROOT / candidate
        if path.exists():
            return path

    raise FileNotFoundError(
        "Не найден JSON сервис-аккаунта Google. Положите credentials.json в корень "
        "проекта или задайте GOOGLE_APPLICATION_CREDENTIALS."
    )

def spreadsheet_id() -> str:
    env = os.getenv("SPREADSHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
    if env:
        return env
    value = _config_attr(("SPREADSHEET_ID", "SHEET_ID", "GS_ID", "GOOGLE_SHEET_ID"))
    return str(value) if value else DEFAULT_SPREADSHEET_ID


def client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(str(_creds_path()), scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def open_spreadsheet():
    return client().open_by_key(spreadsheet_id())


def open_ws(title: str, rows: int = 1000, cols: int = 26, create: bool = True):
    """Открывает лист по имени. При create=True — создаёт, если нет."""
    sh = open_spreadsheet()
    try:
        ws = sh.worksheet(title)
    except gspread.WorksheetNotFound:
        if not create:
            raise
        ws = sh.add_worksheet(title=title, rows=rows, cols=cols)
    if ws.row_count < rows or ws.col_count < cols:
        try:
            ws.resize(rows=max(rows, ws.row_count), cols=max(cols, ws.col_count))
        except Exception as exc:  # noqa: BLE001
            log.warning("resize '%s': %s", title, exc)
    return ws


def read_cell(ws, a1: str) -> str | None:
    try:
        return ws.acell(a1).value
    except Exception:  # noqa: BLE001
        return None


def write_table(ws, header: list, rows: list[list]) -> None:
    """Пишет шапку + строки, начиная с A1. Старое содержимое листа не чистит."""
    values = [list(header)] + [list(r) for r in rows]
    try:
        ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    except TypeError:  # старый gspread
        ws.update("A1", values)