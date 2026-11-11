"""unitka/settings.py — единая точка ручного ввода: лист «НАСТРОЙКИ».

Зачем: до 2026-11-10 ручные данные были разбросаны по пяти листам
(«Ручной ввод», «ДДС Ввод», «План», «Стратегии», «НАСТРОЙКИ»), а пять модулей
держали свою копию get_manual_inputs. Теперь всё, что вводит человек, лежит
на одном листе, а модули читают его через этот файл.

Раскладка листа «НАСТРОЙКИ» (левая часть — параметры «подпись → значение»):
    B1  ставка налога, %            B2/B3  период для «Юнит экономика»
    B4  режим УСН                   B5     взносы ИП за год
    B7  деньги на расчётном счёте   B8     кредиторка поставщикам
    B9  уплачено налогов с начала года
    B10:B14  параметры ABC/XYZ (читает calc_abc_xyz)
    B16 целевая маржа, %            B17    общие расходы Ozon, % (пусто = факт за год)
Параметры B7:B9, B16:B17 ищутся ПО ПОДПИСИ в колонке A, а не по номеру строки.

Блоки-таблицы ищутся по заголовку-якорю в любой ячейке листа; под якорем —
строка заголовков, ниже — данные до первой пустой строки:
    «ПЛАН ПО МЕСЯЦАМ»       Месяц | Тип | Выручка (всего) | …   (читает calc_plan_fact)
    «РАСХОДЫ ПО МЕСЯЦАМ»    Месяц (1-12) | Закупки | Налоги | Личные | Персонал | …
                            (читают calc_cashflow и P&L)
    «СТРАТЕГИЧЕСКИЕ ЦЕЛИ»   Стратегия | Метрика | Цель | Дедлайн | Комментарий
                            (читает calc_strategy)

Обратная совместимость: если на «НАСТРОЙКИ» блока или подписи нет — данные
берутся со старого листа («Ручной ввод», «ДДС Ввод», «План», «Стратегии»).

Правило из брифа: модуль только читает, в таблицу не пишет.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)

SHEET = "НАСТРОЙКИ"
GRID_RANGE = "A1:AK120"

ANCHOR_PLAN = "план по месяцам"
ANCHOR_OUTFLOWS = "расходы по месяцам"
ANCHOR_STRATEGY = "стратегические цели"

DEFAULT_TARGET_MARGIN_PCT = 20.0

# Колонки блока «РАСХОДЫ ПО МЕСЯЦАМ»: ключ → с чего начинается заголовок колонки
OUTFLOW_COLUMNS = (
    ("purchases", "закуп"),
    ("taxes", "налог"),
    ("personal", "личн"),
    ("staff", "персонал"),
    ("admin", "админ"),
    ("commercial", "коммерч"),
    ("other", "проч"),
)


def _norm(v) -> str:
    return str(v if v is not None else "").strip().lower().replace("ё", "е")


def to_float(v):
    """Число из ячейки: 166919.47, «166 919,47 ₽», «5%» → float; пусто/текст → None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = (str(v).replace("\xa0", "").replace(" ", "").replace("₽", "")
         .replace("%", "").replace("−", "-").replace(",", ".").strip())
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _serial_to_date(n: float) -> date:
    """Дата Google Sheets (число дней от 1899-12-30) → date."""
    return date(1899, 12, 30) + timedelta(days=int(n))


def month_key(v) -> str:
    """Месяц из ячейки → 'YYYY-MM'. Понимает дату-число, '2026-11', '2026-11-01', '11.2026', '01.11.2026'."""
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 < v < 80000:
            return _serial_to_date(v).strftime("%Y-%m")
        return ""
    s = str(v).strip()
    if len(s) >= 7 and s[4] == "-" and s[:4].isdigit() and s[5:7].isdigit():
        return s[:7]
    parts = s.split(".")
    if len(parts) == 2 and parts[0].isdigit() and len(parts[1]) == 4:
        return f"{parts[1]}-{int(parts[0]):02d}"
    if len(parts) == 3 and len(parts[2]) == 4 and parts[1].isdigit():
        return f"{parts[2]}-{int(parts[1]):02d}"
    return ""


def date_text(v) -> str:
    """Дата из ячейки → 'YYYY-MM-DD' (если это дата-число), иначе текст как есть."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 20000 < v < 80000:
        return _serial_to_date(v).strftime("%Y-%m-%d")
    return str(v if v is not None else "").strip()


def _cell_text(v) -> str:
    """Значение ячейки → строка без хвоста '.0' у целых."""
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def read_grid(sh, title: str = SHEET, rng: str = GRID_RANGE) -> list:
    """Сырые (неформатированные) значения листа. Нет листа/доступа → []."""
    try:
        ws = sh.worksheet(title)
        return ws.get(rng, value_render_option="UNFORMATTED_VALUE") or []
    except Exception as exc:  # noqa: BLE001
        log.info("Лист «%s» не прочитан (%s)", title, exc)
        return []


def _find_block(grid: list, anchor: str):
    """Ищет ячейку-якорь. Возвращает (header, rows) — заголовки и строки данных под ним."""
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if not _norm(cell).startswith(anchor):
                continue
            if r + 1 >= len(grid):
                return [], []
            head_row = grid[r + 1]
            header = []
            for cc in range(c, len(head_row)):
                if _norm(head_row[cc]) == "":
                    break
                header.append(str(head_row[cc]).strip())
            if not header:
                return [], []
            rows = []
            for rr in range(r + 2, len(grid)):
                line = grid[rr]
                vals = [(line[cc] if cc < len(line) else "") for cc in range(c, c + len(header))]
                if _norm(vals[0]) == "":
                    break
                rows.append(vals)
            return header, rows
    return [], []


def _params(grid: list) -> dict:
    """Параметры «подпись (A) → значение (B)» по всему листу."""
    out = {}
    for row in grid:
        if len(row) >= 2 and _norm(row[0]):
            out[_norm(row[0])] = row[1]
    return out


def _param(params: dict, *prefixes: str):
    for label, val in params.items():
        if any(label.startswith(p) for p in prefixes):
            return val
    return None


def _legacy_manual(sh) -> dict:
    """Старый лист «Ручной ввод» (сопоставление по подстроке, как было во всех модулях)."""
    out = {}
    for row in read_grid(sh, "Ручной ввод", "A1:B20"):
        if len(row) < 2:
            continue
        key, val = _norm(row[0]), to_float(row[1])
        if val is None:
            continue
        if "деньги" in key or "счет" in key:
            out["cash"] = val
        elif "кредиторка" in key or "поставщик" in key:
            out["ap"] = val
        elif "налог" in key or "уплачено" in key:
            out["tax_paid"] = val
    return out


def manual_inputs(sh, grid: list | None = None) -> dict:
    """Ручные остатки: {cash, ap, tax_paid, source}.

    Сначала «НАСТРОЙКИ» (подписи «Деньги на…», «Кредиторка…», «Уплачено налогов…»),
    чего там нет — со старого листа «Ручной ввод».
    """
    grid = read_grid(sh) if grid is None else grid
    params = _params(grid)
    found = {
        "cash": to_float(_param(params, "деньги на")),
        "ap": to_float(_param(params, "кредиторка")),
        "tax_paid": to_float(_param(params, "уплачено налогов")),
    }
    source = SHEET
    if any(v is None for v in found.values()):
        legacy = _legacy_manual(sh)
        for k in found:
            if found[k] is None and k in legacy:
                found[k] = legacy[k]
                source = "Ручной ввод"
    return {
        "cash": found["cash"] or 0.0,
        "ap": found["ap"] or 0.0,
        "tax_paid": found["tax_paid"] or 0.0,
        "source": source,
    }


def unit_params(sh=None, grid: list | None = None) -> dict:
    """Параметры юнит-экономики: {target_margin_pct, overhead_pct}.
    overhead_pct = None → брать фактическую долю общих расходов Ozon за период."""
    out = {"target_margin_pct": DEFAULT_TARGET_MARGIN_PCT, "overhead_pct": None}
    if sh is None and grid is None:
        return out
    grid = read_grid(sh) if grid is None else grid
    params = _params(grid)
    val = to_float(_param(params, "целевая маржа"))
    if val is not None and 0 <= val < 90:
        out["target_margin_pct"] = val
    val = to_float(_param(params, "общие расходы", "реклама и общие"))
    if val is not None and 0 <= val < 90:
        out["overhead_pct"] = val
    return out


def rule_params(sh=None, grid: list | None = None) -> dict:
    """Пороги правил «Плана действий» (unitka/rules.py) с листа «НАСТРОЙКИ».
    Ищутся по подписи в колонке A; если строки нет — ключ не возвращается и
    rules.py берёт значение по умолчанию.
        «Неликвид: дней без продаж»   → dead_stock_days
        «Убыточная маржа, %»          → negative_margin_pct (например −5)
        «Нет в наличии: дней простоя» → oos_lost_days
    """
    out: dict = {}
    if sh is None and grid is None:
        return out
    grid = read_grid(sh) if grid is None else grid
    params = _params(grid)
    val = to_float(_param(params, "неликвид"))
    if val is not None and 1 <= val <= 730:
        out["dead_stock_days"] = int(val)
    val = to_float(_param(params, "убыточная маржа"))
    if val is not None and -100 < val <= 0:
        out["negative_margin_pct"] = val
    val = to_float(_param(params, "нет в наличии"))
    if val is not None and 1 <= val <= 90:
        out["oos_lost_days"] = int(val)
    return out


def plan_rows(sh, grid: list | None = None):
    """Блок «ПЛАН ПО МЕСЯЦАМ» как таблица строк (заголовок + данные) в формате старого
    листа «План»: месяц 'YYYY-MM', числа — строками. Блока нет → None (читать «План»)."""
    grid = read_grid(sh) if grid is None else grid
    header, rows = _find_block(grid, ANCHOR_PLAN)
    if not header or not rows:
        return None
    out = [header]
    for vals in rows:
        month = month_key(vals[0])
        if not month:
            continue
        out.append([month] + [_cell_text(v) for v in vals[1:]])
    return out if len(out) > 1 else None


def outflows(sh, grid: list | None = None):
    """Блок «РАСХОДЫ ПО МЕСЯЦАМ»: {месяц 1..12: {purchases, taxes, personal, staff, admin,
    commercial, other, total}}. Блока нет → None (читать «ДДС Ввод»)."""
    grid = read_grid(sh) if grid is None else grid
    header, rows = _find_block(grid, ANCHOR_OUTFLOWS)
    if not header:
        return None
    cols = {}
    for i, h in enumerate(header[1:], start=1):
        hn = _norm(h)
        for key, prefix in OUTFLOW_COLUMNS:
            if hn.startswith(prefix) and key not in cols:
                cols[key] = i
    out = {}
    for vals in rows:
        m = to_float(vals[0])
        if m is None or not 1 <= int(m) <= 12:
            continue
        rec = {key: abs(to_float(vals[i]) or 0.0) for key, i in cols.items()}
        for key, _ in OUTFLOW_COLUMNS:
            rec.setdefault(key, 0.0)
        rec["total"] = sum(rec[key] for key, _ in OUTFLOW_COLUMNS)
        out[int(m)] = rec
    return out


def strategies(sh, grid: list | None = None):
    """Блок «СТРАТЕГИЧЕСКИЕ ЦЕЛИ»: список {name, metric_key, target, deadline, comment}.
    Блока нет → None (читать лист «Стратегии» по-старому)."""
    grid = read_grid(sh) if grid is None else grid
    header, rows = _find_block(grid, ANCHOR_STRATEGY)
    if not header:
        return None
    out = []
    for vals in rows:
        vals = list(vals) + [""] * 5
        out.append({
            "name": str(vals[0]).strip(),
            "metric_key": _norm(vals[1]),
            "target": to_float(vals[2]),
            "deadline": date_text(vals[3]),
            "comment": str(vals[4] or "").strip(),
        })
    return out
