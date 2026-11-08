"""unitka/report_layout.py — общий каркас отчётных листов «Пульт Ozon».

Все calc_* аналитического блока рисуют лист по одному шаблону:
    1. ГЛАВНОЕ       — 3-5 выводов
    2. СВОДКА        — компактная матрица/таблица
    3. ПРОБЛЕМЫ      — топ-5 по критичности
    4. ЧТО ДЕЛАТЬ    — 3-7 конкретных действий
Плюс отдельный лист «<блок> (все)» — полный список.

Эмодзи заданы через U-escape: при создании файла через PowerShell
here-string литеральные 🔴🟡🟢 могут побиться.
"""
from __future__ import annotations

import logging
from typing import Iterable

from unitka import gsheets

log = logging.getLogger("report_layout")

# Эмодзи-маркеры статуса (безопасны для любой консоли)
RED    = "\U0001F534"   # 🔴
YELLOW = "\U0001F7E1"   # 🟡
GREEN  = "\U0001F7E2"   # 🟢

# Заливки заголовков секций (RGB 0..1)
COLOR_MAIN     = {"red": 0.85, "green": 0.91, "blue": 0.98}
COLOR_SUMMARY  = {"red": 0.93, "green": 0.95, "blue": 0.97}
COLOR_PROBLEMS = {"red": 0.99, "green": 0.86, "blue": 0.86}
COLOR_ACTIONS  = {"red": 0.86, "green": 0.96, "blue": 0.86}

STATUS_COLORS = {
    RED:    {"red": 0.99, "green": 0.80, "blue": 0.80},
    YELLOW: {"red": 0.99, "green": 0.95, "blue": 0.80},
    GREEN:  {"red": 0.86, "green": 0.96, "blue": 0.86},
}


def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s or "A"


def _color_for_title(title: str) -> dict:
    t = title.upper()
    if "ГЛАВНОЕ" in t:
        return COLOR_MAIN
    if "СВОДКА" in t or "МАТРИЦА" in t:
        return COLOR_SUMMARY
    if "ПРОБЛЕМ" in t:
        return COLOR_PROBLEMS
    if "ДЕЛАТЬ" in t or "ДЕЙСТВ" in t:
        return COLOR_ACTIONS
    return COLOR_SUMMARY


def _status_from_text(text: str) -> str | None:
    for s in (RED, YELLOW, GREEN):
        if s in text:
            return s
    return None

def clear_and_resize(ws, min_rows: int = 200, cols: int = 12) -> None:
    """Очищает лист и подгоняет размер под отчёт (без скролла)."""
    ws.clear()
    try:
        if ws.row_count < min_rows or ws.col_count < cols:
            ws.resize(rows=max(min_rows, ws.row_count), cols=max(cols, ws.col_count))
    except Exception as exc:  # noqa: BLE001
        log.warning("resize: %s", exc)


def write_row(ws, row: int, values: list, *, bold: bool = False,
              color: dict | None = None, size: int = 10,
              merge_to: int | None = None) -> int:
    """Пишет одну строку. Возвращает следующий номер строки."""
    if not values:
        return row + 1
    last_col = _col_letter(max(len(values), merge_to or len(values)))

    try:
        ws.update(range_name=f"A{row}", values=[values],
                  value_input_option="USER_ENTERED")
    except TypeError:  # старый gspread
        ws.update(f"A{row}", [values])

    fmt = {}
    if bold or color or size != 10:
        fmt["textFormat"] = {"bold": bold, "fontSize": size}
    if color:
        fmt["backgroundColor"] = color
    if fmt:
        try:
            ws.format(f"A{row}:{last_col}{row}", fmt)
        except Exception as exc:  # noqa: BLE001
            log.debug("format row %s: %s", row, exc)

    if merge_to and merge_to > len(values):
        try:
            ws.merge_cells(f"A{row}:{_col_letter(merge_to)}{row}")
        except Exception:  # noqa: BLE001
            pass
    return row + 1


def write_header(ws, row: int, title: str) -> int:
    """Заголовок секции (ГЛАВНОЕ / СВОДКА / ПРОБЛЕМЫ / ЧТО ДЕЛАТЬ)."""
    r = write_row(ws, row, [title], bold=True, size=12,
                  color=_color_for_title(title), merge_to=8)
    return r + 1


def write_bullets(ws, row: int, bullets: Iterable[str]) -> int:
    """Маркированный список. Цвет строки берётся из эмодзи-маркера."""
    for text in bullets:
        status = _status_from_text(text)
        color = STATUS_COLORS.get(status) if status else None
        row = write_row(ws, row, [text], color=color, merge_to=8)
    return row

def write_table(ws, row: int, header: list, rows: list[list]) -> int:
    """Компактная таблица с шапкой."""
    row = write_row(ws, row, header, bold=True, color=COLOR_SUMMARY)
    for r in rows:
        row = write_row(ws, row, r)
    return row


def write_actions(ws, row: int, actions: list[str]) -> int:
    """Блок «ЧТО ДЕЛАТЬ» — нумерованный, со ссылкой на лист."""
    for idx, text in enumerate(actions, 1):
        row = write_row(ws, row, [f"{idx}. {text}"], merge_to=8)
    return row


def write_empty(ws, row: int) -> int:
    return row + 1


def auto_widths(ws, widths: list[int]) -> None:
    try:
        sheet_id = ws._properties["sheetId"]
        requests = []
        for idx, width in enumerate(widths):
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": idx, "endIndex": idx + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }})
        ws.spreadsheet.batch_update({"requests": requests})
    except Exception as exc:  # noqa: BLE001
        log.debug("auto_widths: %s", exc)


def _main() -> int:
    """Smoke-тест без Google: _col_letter, цвета, эмодзи."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    print("RED   :", repr(RED))
    print("YELLOW:", repr(YELLOW))
    print("GREEN :", repr(GREEN))
    for n in (1, 2, 8, 12, 26, 27):
        print(f"  _col_letter({n:>2}) = {_col_letter(n)}")
    print("_color_for_title('ГЛАВНОЕ')      =", _color_for_title("ГЛАВНОЕ"))
    print("_color_for_title('СВОДКА')       =", _color_for_title("СВОДКА"))
    print("_color_for_title('ПРОБЛЕМЫ')     =", _color_for_title("ПРОБЛЕМЫ"))
    print("_color_for_title('ЧТО ДЕЛАТЬ')   =", _color_for_title("ЧТО ДЕЛАТЬ"))
    print("_status_from_text('... ' + RED)  =", _status_from_text("x " + RED))
    print("_status_from_text('---')         =", _status_from_text("---"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())