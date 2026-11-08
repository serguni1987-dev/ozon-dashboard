"""unitka/calc_strategy.py — стратегические цели и прогресс."""
import os
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
SHEET_TITLE = "Стратегии"


# (ключ, метрика, направление, единица) — как считать текущее значение
STRATEGY_METRICS = {
    "margin_total": ("Маржинальность (всего)", "up", "%"),
    "margin_active": ("Маржинальность (активные)", "up", "%"),
    "liq_share_stock": ("Доля неликвида в товаре", "down", "%"),
    "active_share_revenue": ("Доля активных в выручке", "up", "%"),
    "roi": ("ROI", "up", "%"),
    "conversion": ("Конверсия показ→заказ", "up", "%"),
    "ccc": ("CCC (дней)", "down", "дн"),
    "aov": ("Средний чек (AOV)", "up", "₽"),
    "drr": ("ДРР", "down", "%"),
}


def read_strategy(sh):
    """Читает лист «Стратегии». Возвращает список стратегий."""
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        logger.warning("Лист «Стратегии» не найден")
        return []

    rows = ws.get_all_values()
    if len(rows) < 2:
        return []

    headers = [h.strip().lower() for h in rows[0]]
    result = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        try:
            item = {
                "name": row[0].strip(),
                "metric_key": row[1].strip().lower() if len(row) > 1 else "",
                "target": float(row[2].replace(" ", "").replace(",", ".")) if len(row) > 2 and row[2].strip() else None,
                "deadline": row[3].strip() if len(row) > 3 else "",
                "comment": row[4].strip() if len(row) > 4 else "",
            }
            result.append(item)
        except (ValueError, IndexError):
            continue
    return result


def get_current_kpi(sh):
    """Читает последние KPI из листа «KPI»."""
    try:
        ws = sh.worksheet("KPI")
    except gspread.WorksheetNotFound:
        return {}

    rows = ws.get_all_values()
    result = {}
    for row in rows:
        if len(row) >= 3 and row[0] and row[2]:
            name = row[0].strip()
            try:
                result[name] = float(row[2].replace(" ", "").replace(",", ".").replace("₽", "").replace("%", "").replace("дн", "").strip())
            except ValueError:
                pass
    return result


def calc_progress(strategies, current_kpi):
    """Считает прогресс по каждой стратегии."""
    result = []
    for s in strategies:
        metric = STRATEGY_METRICS.get(s["metric_key"])
        if not metric:
            result.append({**s, "current": None, "progress": None, "status": "⚠️ неверная метрика", "unit": ""})
            continue

        metric_name, direction, unit = metric
        current = current_kpi.get(metric_name)
        target = s["target"]

        if current is None or target is None:
            result.append({**s, "current": current, "progress": None, "status": "—", "unit": unit})
            continue

        # Прогресс: насколько мы приблизились к цели
        # (для 'up' и 'down' — разная логика, но прогресс всегда 0..100)
        if direction == "up":
            # Цель: current >= target. Прогресс = current / target * 100 (но не больше 100)
            progress = min(100, current / target * 100) if target != 0 else 100
            if current >= target:
                status = "🟢 достигнуто"
            elif progress >= 80:
                status = "🟡 близко"
            else:
                status = "🔴 в работе"
        else:  # down
            # Цель: current <= target. Прогресс = target / current * 100
            if current == 0:
                progress = 100
            else:
                progress = min(100, target / current * 100)
            if current <= target:
                status = "🟢 достигнуто"
            elif progress >= 80:
                status = "🟡 близко"
            else:
                status = "🔴 в работе"

        result.append({
            **s,
            "current": round(current, 2),
            "progress": round(progress, 1),
            "status": status,
            "unit": unit,
        })
    return result


def write_to_sheet(sh, strategies_with_progress):
    """Пишет лист «Стратегии» с прогрессом."""
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=50, cols=8)

    values = [
        ["СТРАТЕГИЧЕСКИЕ ЦЕЛИ МАГАЗИНА", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["Стратегия", "Метрика", "Цель", "Текущее", "Прогресс", "Дедлайн", "Статус", "Комментарий"],
        ["", "", "", "", "", "", "", ""],
    ]

    for s in strategies_with_progress:
        target_str = f"{s['target']} {s['unit']}" if s['target'] is not None else "—"
        current_str = f"{s['current']} {s['unit']}" if s['current'] is not None else "—"
        progress_str = f"{s['progress']}%" if s['progress'] is not None else "—"
        values.append([
            s["name"],
            STRATEGY_METRICS.get(s["metric_key"], ("—",))[0],
            target_str,
            current_str,
            progress_str,
            s["deadline"],
            s["status"],
            s["comment"],
        ])

    if not strategies_with_progress:
        values.append(["Пока нет стратегий — заполните лист вручную", "", "", "", "", "", "", ""])

    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")
    logger.info("Лист «%s» обновлён (%s стратегий)", SHEET_TITLE, len(strategies_with_progress))


def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    strategies = read_strategy(sh)
    if not strategies:
        logger.warning("Лист «Стратегии» пуст. Заполните его вручную: Стратегия, Метрика, Цель, Дедлайн, Комментарий")
        # Покажем пример — создадим лист с шаблоном
        try:
            ws = sh.worksheet(SHEET_TITLE)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=SHEET_TITLE, rows=20, cols=8)
        ws.clear()
        ws.update(values=[
            ["Стратегия", "Метрика", "Цель", "Дедлайн", "Комментарий"],
            ["Вывести магазин в маржу 20%", "margin_total", 20, "2027-02-01", "Целевая маржинальность"],
            ["Сократить неликвид до 20%", "liq_share_stock", 20, "2026-12-31", "Распродать залежавшиеся товары"],
            ["Доля активных в выручке > 85%", "active_share_revenue", 85, "2027-01-31", "Сфокусироваться на активных SKU"],
            ["ROI > 200%", "roi", 200, "2027-03-01", "Рентабельность инвестиций"],
        ], range_name="A1", value_input_option="USER_ENTERED")
        logger.info("Создан шаблон листа «Стратегии» — заполните его своими целями")
        return

    current_kpi = get_current_kpi(sh)
    result = calc_progress(strategies, current_kpi)
    write_to_sheet(sh, result)

    for r in result:
        logger.info("  %s: %s → %s (%s)", r["name"], r["current"], r["target"], r["status"])


if __name__ == "__main__":
    main()
