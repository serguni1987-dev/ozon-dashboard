"""unitka/calc_action_plan.py — Умный план действий на основе rules.py.

    py -m unitka.calc_action_plan            пересчитать и записать лист «План действий»
    py -m unitka.calc_action_plan --local    только посчитать и напечатать, без Google Sheets

Цифры паспорта SKU берутся из unit_core (тот же расчёт, что в «Юнит-сводке» и Пульте):
минимальная цена — «в ноль» с комиссией, логистикой и налогом; маржа — после расходов Ozon.
"""
import argparse
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
from .db import connect
from . import config, rules, unit_core

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CRED = str(config.CREDENTIALS)
SHEET_ID = config.SHEET_ID
SHEET_TITLE = "План действий"
N_COLS = 8                      # A:G видит менеджер, H — служебный rule_id (скрыт)
DATA_START_ROW = 3              # индекс первой строки данных (после заголовка, шапки и пустой строки)

# Старые строки листа (до колонки H): правило определяем по началу текста проблемы
_LEGACY_PREFIX = (
    ("Цена", "price_below_min"), ("Нет в наличии", "out_of_stock"),
    ("Неликвид", "dead_stock"), ("Маржинальность", "negative_margin"),
)


def _legacy_rule(problem: str) -> str:
    for prefix, rule_id in _LEGACY_PREFIX:
        if str(problem).startswith(prefix):
            return rule_id
    return ""


def _last_sale_dates(cur) -> dict:
    """Дата последней продажи по SKU: начисления (доставка) и отправления (заказ) — что позже."""
    out = {}
    queries = (
        "SELECT sku, MAX(substr(date,1,10)) FROM accruals "
        "WHERE accrued_category = 'POSTING' AND COALESCE(sale_price,0) > 0 GROUP BY sku",
        "SELECT sku, MAX(substr(date,1,10)) FROM postings_daily "
        "WHERE COALESCE(is_cancelled,0) = 0 GROUP BY sku",
    )
    for sql in queries:
        try:
            cur.execute(sql)
        except Exception:  # noqa: BLE001 — таблицы может не быть в новой базе
            continue
        for sku, d in cur.fetchall():
            if sku in (None, "") or not d:
                continue
            key = str(sku)
            if d > out.get(key, ""):
                out[key] = d
    return out


def _first_stock_dates(cur) -> dict:
    """Первая дата, когда товар появился в остатках (для товаров без единой продажи)."""
    try:
        cur.execute("SELECT sku, MIN(date) FROM stock_daily WHERE fbo_present + fbs_present > 0 GROUP BY sku")
        return {str(sku): d for sku, d in cur.fetchall() if d}
    except Exception:  # noqa: BLE001
        return {}


def _days_since(iso: str, today: date) -> int:
    try:
        return max(0, (today - date.fromisoformat(iso[:10])).days)
    except (TypeError, ValueError):
        return 0


def collect_sku_data(cur, tax=None, unit=None, today=None):
    """Собирает паспорта всех активных SKU для проверки правилами.

    tax  — finance_core.tax_settings(sh), unit — settings.unit_params(sh); без них — значения по умолчанию.
    today — дата расчёта (по умолчанию сегодня); нужна для проверки на старой копии базы.

    Поля паспорта:
        price          текущая цена из current_prices (цена с акциями продавца, иначе обычная)
        min_price      мин. цена «в ноль» (unit_core.min_prices → min_direct): себестоимость,
                       комиссия по тарифу, логистика на штуку, эквайринг, налог
        margin_pct     маржа за 30 дней ПОСЛЕ комиссии и услуг Ozon и себестоимости, % от дохода
                       (без общих расходов магазина — реклама и подписки не привязаны к SKU)
        revenue_30d    доход за 30 дней (как в P&L: цена + баллы + софинансирование)
        sold_14d       доставлено штук за 14 дней (факт, а не «половина от 30 дней»)
        days_no_sales  дней с последней продажи; если продаж не было — с первого появления на складе
    """
    today = today or date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()
    d30 = (today - timedelta(days=30)).isoformat()
    d14 = (today - timedelta(days=14)).isoformat()

    # 1. Мин. цены и текущие цены — по экономике с начала года (как в «Юнит-сводке»)
    eco_year = unit_core.sku_economics(cur, f"{today.year}-01-01", f"{today.year + 1}-01-01")
    mins = unit_core.min_prices(cur, eco_year, tax, unit)

    # 2. Маржа за 30 дней и продажи за 14 дней — тот же расчёт на коротком периоде
    eco_30 = unit_core.sku_economics(cur, d30, tomorrow)["skus"]
    eco_14 = unit_core.sku_economics(cur, d14, tomorrow)["skus"]

    last_sale = _last_sale_dates(cur)
    first_stock = _first_stock_dates(cur)

    result = []
    for sku, y in eco_year["skus"].items():
        s30 = eco_30.get(sku)
        stock = int(y.get("stock") or 0)
        delivered_30 = (s30 or {}).get("delivered", 0)
        if stock <= 0 and delivered_30 <= 0:
            continue                                    # не на складе и не продавался за 30 дней
        m = mins.get(sku, {})
        key = str(sku)
        revenue = (s30 or {}).get("income", 0.0)
        cost = y.get("cost_unit", 0.0)
        # Маржу считаем только там, где известна себестоимость: без неё получится «фейковая прибыль»
        margin_pct = (s30["direct_profit"] / revenue * 100) if s30 and revenue > 0 and cost > 0 else 0.0
        price = m.get("price") or 0.0
        avg_price = (revenue / delivered_30) if delivered_30 > 0 and revenue > 0 else price
        ref = last_sale.get(key) or first_stock.get(key)
        result.append({
            "sku": key,
            "offer_id": y.get("offer_id") or "",
            "stock": stock,
            "cost": cost,
            "price": price,
            "min_price": m.get("min_direct") or 0.0,
            "revenue_30d": revenue,
            "margin_pct": margin_pct,
            "sold_14d": int(round((eco_14.get(sku) or {}).get("delivered", 0))),
            "avg_price": avg_price,
            "days_no_sales": _days_since(ref, today) if ref else 0,
        })
    return result


def build_tasks(cur, tax=None, unit=None, thresholds=None, today=None):
    """Паспорта SKU → правила → задачи, отсортированные по деньгам. Только читает БД."""
    rules.set_thresholds(thresholds)
    all_tasks = []
    for sku_data in collect_sku_data(cur, tax, unit, today):
        all_tasks.extend(rules.evaluate_sku(sku_data))
    all_tasks.sort(key=lambda t: t.money_impact, reverse=True)
    return all_tasks


def severity_label(severity: int) -> str:
    return "🔴 КРИТИЧНО" if severity == 1 else ("🟡 ВАЖНО" if severity == 2 else "🟢 ИНФО")


def main():
    ap = argparse.ArgumentParser(description="Умный план действий")
    ap.add_argument("--local", action="store_true", help="без Google Sheets: посчитать и напечатать")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    if args.local:
        all_tasks = build_tasks(cur)
        conn.close()
        for t in all_tasks:
            print(f"{severity_label(t.severity)} | {t.offer_id or t.sku} | {t.problem} | {t.action} | {t.money_impact:,.0f} ₽")
        print(f"Найдено проблем: {len(all_tasks)}, сумма: {sum(t.money_impact for t in all_tasks):,.0f} ₽ (--local, лист не обновлялся)")
        return

    # Настройки с листа «НАСТРОЙКИ»: налог, целевая маржа, пороги правил
    from . import settings
    from .finance_core import tax_settings
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    try:
        grid = settings.read_grid(sh)
        unit, thresholds = settings.unit_params(grid=grid), settings.rule_params(grid=grid)
    except Exception as exc:  # noqa: BLE001
        print(f"НАСТРОЙКИ не прочитаны ({exc}) — пороги по умолчанию")
        unit, thresholds = None, None

    print("Сбор данных по SKU и проверка правил...")
    all_tasks = build_tasks(cur, tax_settings(sh), unit, thresholds)
    conn.close()

    # Читаем старые статусы, чтобы не потерять их при перезаписи.
    # Ключ — правило + SKU (колонка H), а не текст проблемы: текст меняется вместе с ценой,
    # и статус «в работе» раньше сбрасывался при изменении цены на рубль.
    existing_statuses = {}
    try:
        ws_old = sh.worksheet(SHEET_TITLE)
        old_data = ws_old.get_all_values()
        for row in old_data[DATA_START_ROW:]:
            if len(row) >= 7 and row[2]:
                rule_id = (row[7] if len(row) >= 8 else "") or _legacy_rule(row[3])
                if rule_id:
                    existing_statuses[f"{rule_id}_{row[2]}"] = row[6]   # G — Статус
    except gspread.WorksheetNotFound:
        pass

    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=N_COLS)

    now_str = date.today().strftime("%Y-%m-%d")
    rows = [
        [f"УМНЫЙ ПЛАН ДЕЙСТВИЙ — {now_str}"],
        ["Срочность", "Артикул", "SKU", "Проблема", "Что делать", "Эффект, ₽", "Статус", "rule_id"],
        []
    ]

    for t in all_tasks:
        status = existing_statuses.get(f"{t.rule_id}_{t.sku}") or "🆕 Новая"
        rows.append([
            severity_label(t.severity), t.offer_id, t.sku, t.problem, t.action,
            round(t.money_impact, 2), status, t.rule_id
        ])

    # Лист мог быть создан на 7 колонок и 200 строк — расширяем, иначе запись упадёт
    if ws.col_count < N_COLS or ws.row_count < len(rows):
        ws.resize(rows=max(ws.row_count, len(rows) + 20), cols=max(ws.col_count, N_COLS))

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")

    # Форматирование
    reqs = [
        {"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 7},
         "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
         "fields": "userEnteredFormat"}},
        {"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 7},
         "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
         "fields": "userEnteredFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 5}, "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 8}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}}
    ]
    sh.batch_update({"requests": reqs})

    print(f"УСПЕХ! Найдено проблем: {len(all_tasks)}")
    print(f"Общий эффект: {sum(t.money_impact for t in all_tasks):,.0f} ₽")
    print("Лист 'План действий' обновлен (статусы сохранены).")

if __name__ == "__main__":
    main()