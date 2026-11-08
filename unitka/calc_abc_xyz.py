"""unitka/calc_abc_xyz.py — лист «ABC/XYZ» в отчётном формате."""
from __future__ import annotations

import argparse
import csv
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from unitka import analytics_db, gsheets, report_layout as rl

log = logging.getLogger("calc_abc_xyz")

SHEET_TITLE      = "ABC/XYZ"
SHEET_FULL_TITLE = "ABC/XYZ (все)"
SETTINGS_TITLE   = "НАСТРОЙКИ"
OUT_DIR          = Path(__file__).resolve().parent.parent / "out"

HEADER_FULL = [
    "SKU", "ABC", "XYZ", "Матрица",
    "Выручка", "Прибыль", "Кол-во",
    "Доля прибыли, %", "Накопл. доля, %",
    "Актив. месяцев", "CV, %",
    "Капитал в SKU", "Рекомендация",
]

RECOMMENDATIONS = {
    "AX": "Ядро. Не трогать, всегда в наличии.",
    "AY": "Сезонный локомотив. Прогнозировать закупки.",
    "AZ": "Высокий вклад, но нестабильно. Проверить сезон/цену.",
    "BX": "Стабильный средний. Оптимизировать закупки.",
    "BY": "Средний сезонный. Планировать по сезону.",
    "BZ": "Средний нестабильный. Проверить причину скачков.",
    "CX": "Малый вклад, стабильный. Оставить, если не тянет ресурсы.",
    "CY": "Малый вклад, сезонный. Не закупать сверх сезона.",
    "CZ": "Кандидат на вывод. Капитал здесь — неликвид.",
}

ABC_THRESHOLDS = (0.80, 0.95)
XYZ_THRESHOLDS = (10.0, 25.0)

DEFAULT_SETTINGS = {
    "top_n": 10,
    "cz_capital": 100_000.0,
    "cv_threshold": 25.0,
    "cz_min": 5,
    "min_active_months": 3,
}


def _read_settings() -> dict:
    result = dict(DEFAULT_SETTINGS)
    try:
        ws = gsheets.open_ws(SETTINGS_TITLE, create=False)
    except Exception as exc:
        log.info("НАСТРОЙКИ недоступны (%s) — значения по умолчанию", exc)
        return result
    for cell, key, cast in (
        ("B10", "top_n", int),
        ("B11", "cz_capital", float),
        ("B12", "cv_threshold", float),
        ("B13", "cz_min", int),
        ("B14", "min_active_months", int),
    ):
        raw = gsheets.read_cell(ws, cell)
        if not raw:
            continue
        try:
            result[key] = cast(float(str(raw).replace(",", ".")))
        except (TypeError, ValueError):
            log.warning("НАСТРОЙКИ!%s = %r не число", cell, raw)
    return result

def _load_profit_data(conn, dfrom: str, dto: str) -> dict:
    data = {}
    try:
        for r in conn.execute("""
            SELECT sku, SUM(quantity * price) AS revenue,
                   SUM(commission) AS commission, SUM(quantity) AS qty
            FROM postings_daily
            WHERE date BETWEEN ? AND ?
              AND COALESCE(is_cancelled,0)=0 AND COALESCE(is_returned,0)=0
            GROUP BY sku
        """, (dfrom, dto)):
            s = int(r["sku"])
            data[s] = {
                "revenue": float(r["revenue"] or 0.0),
                "commission": float(r["commission"] or 0.0),
                "qty": int(r["qty"] or 0),
                "cost": 0.0,
                "services": 0.0,
            }
    except Exception as exc:
        log.warning("postings_daily: %s", exc)
        return {}

    if not data:
        return {}

    try:
        for r in conn.execute("""
            SELECT p.sku,
                   SUM(p.quantity * COALESCE(
                       (SELECT pch.cost_price FROM product_cost_history pch
                         WHERE pch.sku=p.sku AND pch.date_from<=p.date
                         ORDER BY pch.date_from DESC LIMIT 1), 0)) AS cost
            FROM postings_daily p
            WHERE p.date BETWEEN ? AND ?
              AND COALESCE(p.is_cancelled,0)=0 AND COALESCE(p.is_returned,0)=0
            GROUP BY p.sku
        """, (dfrom, dto)):
            s = int(r["sku"])
            if s in data:
                data[s]["cost"] = float(r["cost"] or 0.0)
    except Exception as exc:
        log.warning("product_cost_history: %s", exc)

    try:
        for r in conn.execute("""
            SELECT sku, SUM(amount) AS s FROM accrual_sku_daily
            WHERE date BETWEEN ? AND ? GROUP BY sku
        """, (dfrom, dto)):
            s = int(r["sku"])
            if s in data:
                data[s]["services"] = float(r["s"] or 0.0)
    except Exception as exc:
        log.debug("accrual_sku_daily: %s", exc)

    return data


def _load_active_months(conn, dfrom: str, dto: str) -> dict:
    result = defaultdict(dict)
    try:
        for r in conn.execute("""
            SELECT sku, substr(date,1,7) AS m, SUM(quantity*price) AS rev
            FROM postings_daily
            WHERE date BETWEEN ? AND ? AND COALESCE(is_cancelled,0)=0
            GROUP BY sku, substr(date,1,7)
        """, (dfrom, dto)):
            s = int(r["sku"])
            v = float(r["rev"] or 0.0)
            if v > 0:
                result[s][str(r["m"])] = v
    except Exception as exc:
        log.warning("postings (monthly): %s", exc)
    return dict(result)


def _load_capital(conn) -> tuple:
    result = {}
    any_data = False
    try:
        # Используем stock_daily (10-значные SKU), а не current_stocks
        cur_date = conn.execute("SELECT MAX(date) FROM stock_daily").fetchone()[0]
        if not cur_date:
            return result, False
            
        for r in conn.execute("""
            SELECT sd.sku,
                   SUM((sd.fbo_present + sd.fbs_present) * COALESCE(
                       (SELECT pch.cost_price FROM product_cost_history pch
                         WHERE pch.sku=sd.sku AND pch.date_from <= sd.date
                         ORDER BY pch.date_from DESC LIMIT 1), 0)) AS cap
            FROM stock_daily sd 
            WHERE sd.date = ?
            GROUP BY sd.sku
        """, (cur_date,)):
            cap = float(r["cap"] or 0.0)
            if cap > 0:
                any_data = True
            result[int(r["sku"])] = cap
    except Exception as exc:
        log.debug("stock_daily: %s", exc)
    return result, any_data

def _cv(values: list) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean <= 0:
        return None
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return round((var ** 0.5) / mean * 100, 1)


def _classify_abc(profit_sorted: list) -> dict:
    total = sum(max(p, 0.0) for _, p in profit_sorted)
    out = {}
    if total <= 0:
        for sku, _ in profit_sorted:
            out[sku] = ("C", 0.0, 0.0)
        return out
    a_thr, b_thr = ABC_THRESHOLDS
    cum = 0.0
    for sku, profit in profit_sorted:
        share = max(profit, 0.0) / total
        cum += share
        cls = "A" if cum <= a_thr else ("B" if cum <= b_thr else "C")
        out[sku] = (cls, round(share * 100, 2), round(cum * 100, 2))
    return out


def _classify_xyz(cv: float | None, active_months: int,
                   min_active: int, cv_threshold: float) -> tuple:
    if active_months < min_active:
        return "N/A", "Мало истории"
    if cv is None:
        return "N/A", "Эпизодический"
    x_thr = XYZ_THRESHOLDS[0]
    y_thr = max(XYZ_THRESHOLDS[1], cv_threshold)
    if cv <= x_thr:
        return "X", None
    if cv <= y_thr:
        return "Y", None
    return "Z", None


def _compute(dfrom: date, dto: date, settings: dict) -> dict:
    conn = analytics_db.connect()
    analytics_db.ensure_schema(conn)

    dfrom_s, dto_s = dfrom.isoformat(), dto.isoformat()
    profit_data = _load_profit_data(conn, dfrom_s, dto_s)
    if not profit_data:
        log.warning("Нет данных за %s..%s", dfrom_s, dto_s)
        return {}

    active = _load_active_months(conn, dfrom_s, dto_s)
    capital, capital_available = _load_capital(conn)
    min_active = settings["min_active_months"]

    profits = {s: d["revenue"] - d["cost"] - d["commission"] - d["services"]
               for s, d in profit_data.items()}
    profit_sorted = sorted(profits.items(), key=lambda kv: kv[1], reverse=True)
    abc = _classify_abc(profit_sorted)

    items = []
    for sku, profit in profit_sorted:
        abc_cls, share, cum = abc[sku]
        months_rev = active.get(sku, {})
        active_months = len(months_rev)
        cv = _cv(list(months_rev.values())) if active_months >= 2 else None
        xyz_cls, reason = _classify_xyz(cv, active_months, min_active, settings["cv_threshold"])
        matrix = f"{abc_cls}{xyz_cls}" if xyz_cls in ("X", "Y", "Z") else "N/A"
        items.append({
            "sku": sku, "abc": abc_cls, "xyz": xyz_cls, "matrix": matrix,
            "revenue": profit_data[sku]["revenue"], "profit": profit,
            "qty": profit_data[sku]["qty"], "share": share, "cum": cum,
            "active_months": active_months, "cv": cv,
            "capital": capital.get(sku, 0.0),
            "recommendation": RECOMMENDATIONS.get(matrix, "—"),
            "reason": reason,
        })

    total_profit  = sum(max(i["profit"], 0.0) for i in items) or 1.0
    total_revenue = sum(i["revenue"] for i in items)

    items_real     = [i for i in items if i["xyz"] in ("X", "Y", "Z")]
    items_few_data = [i for i in items if i["xyz"] == "N/A"]
    items_expenses = [i for i in items if i["revenue"] <= 0]

    matrix = {a: {x: [] for x in ("X", "Y", "Z", "N/A")} for a in "ABC"}
    for i in items:
        matrix[i["abc"]][i["xyz"]].append(i)

    period = f"{dfrom_s}_{dto_s}"
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("DELETE FROM abc_xyz WHERE period = ?", (period,))
    conn.executemany("""
        INSERT INTO abc_xyz (period, sku, profit, revenue, qty,
            abc_class, xyz_class, matrix, share_profit, cum_share, cv,
            capital, recommendation, fetched_at, active_months, reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        period, i["sku"], i["profit"], i["revenue"], i["qty"],
        i["abc"], i["xyz"], i["matrix"], i["share"], i["cum"], i["cv"],
        i["capital"], i["recommendation"], fetched_at,
        i["active_months"], i["reason"]
    ) for i in items])
    conn.commit()

    return {
        "period": period, "dfrom": dfrom_s, "dto": dto_s,
        "items": items,
        "items_real": items_real,
        "items_few_data": items_few_data,
        "items_expenses": items_expenses,
        "matrix": matrix,
        "total_profit": total_profit, "total_revenue": total_revenue,
        "capital_available": any(i["capital"] > 0 for i in items),
        "min_active": min_active,
        "settings": settings,
    }

def _fmt_money(x: float) -> str:
    return f"{x:,.0f} ₽".replace(",", " ")


def _build_report(data: dict) -> tuple:
    items_real     = data["items_real"]
    items_few_data = data["items_few_data"]
    matrix         = data["matrix"]
    s              = data["settings"]
    cap_ok         = data["capital_available"]

    ax = matrix["A"]["X"]; ay = matrix["A"]["Y"]; az = matrix["A"]["Z"]
    cz = matrix["C"]["Z"]; bz = matrix["B"]["Z"]

    ax_share   = sum(i["share"] for i in ax)
    cz_capital = sum(i["capital"] for i in cz) if cap_ok else None
    az_sku     = [i for i in az if i["profit"] > 0]

    main = []
    
    total_profit_all = sum(max(i["profit"], 0.0) for i in data["items"]) or 1.0
    a_items = [i for i in data["items"] if i["abc"] == "A"]
    a_profit = sum(max(i["profit"], 0.0) for i in a_items)
    a_share = int((a_profit / total_profit_all) * 100) if total_profit_all > 0 else 0
    if a_items:
        main.append(f"{rl.GREEN} A-класс = {len(a_items)} SKU = {a_share}% прибыли")
    else:
        main.append(f"{rl.YELLOW} A-класс не сформирован (нет данных)")

    if ax:
        main.append(f"{rl.GREEN} {len(ax)} SKU в ядре (AX) — {ax_share:.0f}% прибыли. "
                    f"Держать в наличии постоянно.")
    if az_sku:
        main.append(f"{rl.YELLOW} {len(az_sku)} SKU в AZ — прибыль есть, "
                    f"но продажи скачут (CV > {s['cv_threshold']:.0f}%). "
                    f"Проверить сезон / цену.")
    if items_few_data:
        main.append(f"{rl.YELLOW} {len(items_few_data)} SKU — мало истории "
                    f"(< {s['min_active_months']} мес продаж). "
                    f"Не оцениваются по стабильности, наблюдать.")
    if cz:
        if cap_ok and cz_capital is not None:
            main.append(f"{rl.RED} {len(cz)} SKU в CZ — {_fmt_money(cz_capital)} "
                        f"капитала, продаж почти нет. Кандидаты на вывод.")
        else:
            main.append(f"{rl.RED} {len(cz)} SKU в CZ — продаж почти нет. "
                        f"Кандидаты на вывод (капитал: нет данных по себестоимости).")
    if not main:
        main.append(f"{rl.GREEN} Матрица не сформирована: "
                    f"у всех SKU недостаточно истории. Наблюдать.")

    summary = [["", "X (стабильно)", "Y (сезонно)", "Z (скачет)",
                "N/A (мало данных)", "Итого"]]
    for a in "ABC":
        row = [a]
        for x in ("X", "Y", "Z", "N/A"):
            group = matrix[a][x]
            share = sum(i["share"] for i in group)
            row.append(f"{len(group)} SKU / {share:.0f}%")
        row.append(str(sum(len(matrix[a][x]) for x in ("X", "Y", "Z", "N/A"))))
        summary.append(row)

    problems = []
    if cz:
        cz_sorted = sorted(cz, key=lambda i: (i["capital"] if cap_ok else 0), reverse=True)
        for i in cz_sorted[:3]:
            if cap_ok and i["capital"] > 0:
                problems.append(
                    f"{rl.RED} SKU {i['sku']} (CZ) — капитал {_fmt_money(i['capital'])}, "
                    f"продаж {i['qty']} шт. Выводить."
                )
            else:
                problems.append(
                    f"{rl.RED} SKU {i['sku']} (CZ) — продаж {i['qty']} шт, "
                    f"капитал: нет данных. Проверить и выводить."
                )
    for i in sorted(az_sku, key=lambda i: i["profit"], reverse=True)[:2]:
        if i["cv"] is not None:
            problems.append(
                f"{rl.YELLOW} SKU {i['sku']} (AZ) — прибыль {_fmt_money(i['profit'])}, "
                f"CV={i['cv']:.0f}%. Проверить сезон / цену."
            )
    if not problems:
        problems.append(f"{rl.GREEN} Критичных проблем не обнаружено. Продолжать мониторинг.")

    actions = []
    if ax:
        actions.append(f"Не трогать {len(ax)} SKU ядра (AX) — это "
                       f"{ax_share:.0f}% прибыли. Следить за остатками "
                       f"(лист «Оборачиваемость»).")
    if cz:
        if cap_ok and cz_capital is not None and cz_capital > 0:
            actions.append(f"Вывести {len(cz)} SKU из CZ — освободит "
                           f"{_fmt_money(cz_capital)} (сверить с «Деньгами в товаре»).")
        else:
            actions.append(f"Проверить {len(cz)} SKU из CZ — продаж нет. "
                           f"Решение по выводу (данные по капиталу неполные).")
    if az_sku:
        actions.append(f"По {len(az_sku)} SKU из AZ — проверить сезонность и цены "
                       f"(листы «Оборачиваемость» и «Цены»).")
    if items_few_data:
        actions.append(f"{len(items_few_data)} SKU с малой историей — "
                       f"наблюдать 2-3 месяца, потом пересмотреть класс.")
    actions.append(f"Топ-{s['top_n']} по прибыли — не менять цену/акции без A/B-теста.")

    return main, summary, problems, actions


def _build_full_rows(data: dict) -> list:
    rows = []
    for i in data["items"]:
        cap_val = round(i["capital"], 2) if i["capital"] else ""
        rows.append([
            i["sku"], i["abc"], i["xyz"], i["matrix"],
            round(i["revenue"], 2), round(i["profit"], 2), i["qty"],
            i["share"], i["cum"],
            i["active_months"],
            i["cv"] if i["cv"] is not None else "",
            cap_val,
            i["recommendation"],
        ])
    return rows

def _write_main_sheet(ws, data: dict) -> int:
    main, summary, problems, actions = _build_report(data)
    rl.clear_and_resize(ws, min_rows=80, cols=12)

    row = 1
    row = rl.write_row(ws, row, [f"ABC/XYZ — {data['dfrom']} .. {data['dto']}"],
                       bold=True, size=14, color=rl.COLOR_MAIN, merge_to=6)
    row = rl.write_empty(ws, row)
    row = rl.write_header(ws, row, "ГЛАВНОЕ")
    row = rl.write_bullets(ws, row, main)
    row = rl.write_empty(ws, row)
    row = rl.write_header(ws, row, "СВОДКА — матрица 3x3")
    row = rl.write_table(ws, row, summary[0], summary[1:])
    row = rl.write_empty(ws, row)
    row = rl.write_header(ws, row, "ПРОБЛЕМЫ — топ-5")
    row = rl.write_bullets(ws, row, problems)
    row = rl.write_empty(ws, row)
    row = rl.write_header(ws, row, "ЧТО ДЕЛАТЬ")
    row = rl.write_actions(ws, row, actions)

    rl.auto_widths(ws, [140, 160, 160, 140, 90, 90, 90, 90])
    return row


def _write_full_sheet(ws, data: dict) -> None:
    """Записывает полный список ОДНИМ batch-запросом (оптимизация под квоту Google)."""
    rows = _build_full_rows(data)
    
    # 1. Очищаем лист
    ws.clear()
    
    # 2. Формируем все значения: заголовок + строки
    all_values = [HEADER_FULL] + rows
    
    # 3. Один запрос на запись всех данных
    ws.update(values=all_values, range_name="A1")
    
    # 4. Одно форматирование (batch)
    n_rows = len(all_values)
    fmt_requests = [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(HEADER_FULL)},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": n_rows, "startColumnIndex": 4, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": n_rows, "startColumnIndex": 7, "endColumnIndex": 10},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}}},
            "fields": "userEnteredFormat.numberFormat"
        }},
        # Ширины колонок
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 110}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 4}, "properties": {"pixelSize": 60}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 7}, "properties": {"pixelSize": 110}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 11}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 11, "endIndex": 13}, "properties": {"pixelSize": 130}, "fields": "pixelSize"}},
    ]
    ws.spreadsheet.batch_update({"requests": fmt_requests})


def main(argv: list | None = None) -> int:
    today = date.today()
    p = argparse.ArgumentParser(description="Лист «ABC/XYZ» (отчётный формат)")
    p.add_argument("--from", dest="dfrom",
                   default=(today - timedelta(days=270)).isoformat())
    p.add_argument("--to", dest="dto",
                   default=(today - timedelta(days=1)).isoformat())
    p.add_argument("--local", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")

    dfrom, dto = date.fromisoformat(args.dfrom), date.fromisoformat(args.dto)
    settings = _read_settings()
    log.info("Период %s..%s, settings=%s", dfrom, dto, settings)

    data = _compute(dfrom, dto, settings)
    if not data:
        log.error("Пустой результат")
        return 1

    main_lines, summary, problems, actions = _build_report(data)

    na_total = len(data["items_few_data"])
    low_hist = sum(1 for i in data["items_few_data"] if i.get("reason") == "Мало истории")
    episodic = na_total - low_hist
    log.info("ABC/XYZ: матрица=%s (X/Y/Z: %s, N/A: %s)", len(data["items"]), len(data["items_real"]), na_total)
    log.info("N/A разбивка: Мало истории=%s, Эпизодический=%s", low_hist, episodic)
    log.info("SKU: всего=%s, в матрице=%s, мало данных=%s, только расходы=%s, капитал=%s",
             len(data["items"]), len(data["items_real"]),
             len(data["items_few_data"]), len(data["items_expenses"]),
             "есть" if data["capital_available"] else "нет")

    if args.local:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"abc_xyz_report_{dfrom}_{dto}.txt"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(f"ABC/XYZ — {dfrom} .. {dto}\n\n")
            fh.write(f"SKU всего: {len(data['items'])}\n")
            fh.write(f"  в матрице (X/Y/Z): {len(data['items_real'])}\n")
            fh.write(f"  мало данных (N/A): {len(data['items_few_data'])}\n")
            fh.write(f"  только расходы:    {len(data['items_expenses'])}\n")
            fh.write(f"  капитал:           {'есть данные' if data['capital_available'] else 'нет данных'}\n\n")
            fh.write("ГЛАВНОЕ:\n")
            for line in main_lines:
                fh.write(f"  {line}\n")
            fh.write("\nСВОДКА:\n")
            for r in summary:
                fh.write("  " + " | ".join(str(c) for c in r) + "\n")
            fh.write("\nПРОБЛЕМЫ:\n")
            for line in problems:
                fh.write(f"  {line}\n")
            fh.write("\nЧТО ДЕЛАТЬ:\n")
            for a in actions:
                fh.write(f"  {a}\n")

        full_path = OUT_DIR / f"abc_xyz_full_{dfrom}_{dto}.csv"
        with full_path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(HEADER_FULL)
            w.writerows(_build_full_rows(data))
        log.info("Отчёт: %s", path)
        log.info("Полный список: %s (%s строк)", full_path, len(data["items"]))
        return 0

    ws = gsheets.open_ws(SHEET_TITLE, create=True)
    _write_main_sheet(ws, data)
    log.info("Лист «%s» обновлён", SHEET_TITLE)

    ws_full = gsheets.open_ws(SHEET_FULL_TITLE, create=True)
    _write_full_sheet(ws_full, data)
    log.info("Лист «%s» обновлён: %s строк", SHEET_FULL_TITLE, len(data["items"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


