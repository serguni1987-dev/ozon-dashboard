"""unitka/finance_core.py — единый расчёт P&L по данным Ozon из БД.

Зачем: до 2026-11-08 четыре модуля (calc_taxes, calc_dashboard,
calc_working_capital, calc_plan_fact) считали «прибыль» как
    доходы (валовые, ДО комиссии) − удержания (БЕЗ комиссии) − себестоимость
и теряли комиссию Ozon (~780 тыс. ₽ за 2026). Здесь — одна проверенная
формула, сверенная с кассой (выплаты Ozon + баланс) и с P&L.

Правила (из брифа): модуль только читает БД, в Sheets не пишет.

Использование:
    from unitka.finance_core import ozon_pnl, tax_rate_pct
    p = ozon_pnl(cur, "2026-01-01", "2027-01-01")
    p["income"]          валовые доходы (цена + баллы + партнёры), как в ЛК Ozon
    p["commission"]      вознаграждение Ozon (из accruals.sale_commission)
    p["services"]        прочие удержания (логистика, реклама, эквайринг …)
    p["ozon_total"]      всё, что оставил себе Ozon = income − net_from_ozon
    p["net_from_ozon"]   что реально причитается продавцу (начислено − удержано)
    p["cogs"]            себестоимость проданного С УЧЁТОМ возвратов
    p["gross_profit"]    net_from_ozon − cogs  (= ВАЛОВАЯ ПРИБЫЛЬ в P&L)
    p["margin_pct"]      gross_profit / income × 100
    p["cogs_missing"]    True, если за период есть продажи, но себестоимость = 0
    p["cogs_estimated"]  True, если часть себестоимости оценена по начислениям (месяц не закрыт)
"""
from __future__ import annotations

import logging
from datetime import date

log = logging.getLogger(__name__)

DEFAULT_TAX_RATE_PCT = 5.0  # УСН «доходы − расходы», ставка по умолчанию (НАСТРОЙКИ!B1 имеет приоритет)

_COST_LATEST = """
    SELECT sku, cost_price FROM product_cost_history
    WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
"""


def _one(cur, sql: str, params: tuple) -> float:
    cur.execute(sql, params)
    row = cur.fetchone()
    return float(row[0] or 0.0) if row else 0.0


def _month_bounds(date_from: str, date_to: str):
    """Список месяцев 'YYYY-MM', целиком входящих в [date_from, date_to)."""
    months = []
    y, m = int(date_from[:4]), int(date_from[5:7])
    while True:
        start = f"{y:04d}-{m:02d}-01"
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        end = f"{ny:04d}-{nm:02d}-01"
        if start >= date_to:
            break
        if start >= date_from and end <= date_to:
            months.append((start[:7], start, end))
        y, m = ny, nm
    return months


def _income_commission(cur, date_from: str, date_to: str):
    """Валовые доходы и комиссия Ozon: закрытые месяцы из monthly_reports, остальное из accruals."""
    rng = (date_from, date_to)
    income_acc_sql = """
        SELECT COALESCE(SUM(COALESCE(sale_price,0) + COALESCE(bonus,0) + COALESCE(coinvestment,0)), 0)
        FROM accruals WHERE date >= ? AND date < ?"""
    comm_acc_sql = """
        SELECT COALESCE(SUM(COALESCE(sale_commission,0)), 0)
        FROM accruals WHERE date >= ? AND date < ?"""

    income = _one(cur, income_acc_sql, rng)
    commission = abs(_one(cur, comm_acc_sql, rng))

    try:
        cur.execute("SELECT month, sale_price_sum + bonus_sum + coinvestment_sum, gross_commission_sum FROM monthly_reports")
        reports = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in cur.fetchall()}
    except Exception:
        return income, commission

    for month, start, end in _month_bounds(date_from, date_to):
        if month not in reports:
            continue
        # заменяем месяц из accruals на месяц из отчёта о реализации
        income -= _one(cur, income_acc_sql, (start, end))
        commission -= abs(_one(cur, comm_acc_sql, (start, end)))
        income += reports[month][0]
        commission += abs(reports[month][1])
    return income, commission


def ozon_pnl(cur, date_from: str, date_to: str) -> dict:
    """P&L по Ozon за [date_from, date_to). Даты — ISO 'YYYY-MM-DD'."""
    rng = (date_from, date_to)

    # Доходы и комиссия: для закрытых месяцев — из отчёта о реализации (monthly_reports,
    # совпадает с ЛК и Точкой до копейки), для открытых — из начислений accruals.
    # В accruals за янв/апр/авг доходы ниже отчёта о реализации на 37 236 ₽ (часть
    # начислений не попала в выгрузку), поэтому отчёт о реализации — приоритетный источник.
    income, commission = _income_commission(cur, date_from, date_to)

    services = abs(_one(cur, """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE type = 'deduction' AND date >= ? AND date < ?""", rng))

    # Что реально причитается продавцу: начисления уже за вычетом комиссии, минус удержания.
    net_from_ozon = _one(cur, """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE date >= ? AND date < ?""", rng)

    ozon_total = income - net_from_ozon  # комиссия + услуги + корректировки по возвратам

    # Себестоимость с учётом возвратов: по месячным отчётам о реализации (закрытые месяцы),
    # по дневной реализации — для месяцев, которых ещё нет в monthly_realization_rows.
    m_from, m_to = date_from[:7], date_to[:7]
    # В monthly_realization_rows quantity = кол-во доставленных (delivery_commission.quantity),
    # возвраты лежат только в raw_json (return_commission.quantity); строка «только возврат»
    # имеет quantity = 0. Поэтому нетто-штуки считаем как доставлено − возвращено из raw_json.
    cogs_monthly = _one(cur, f"""
        SELECT COALESCE(SUM(
            (COALESCE(json_extract(m.raw_json, '$.delivery_commission.quantity'), m.quantity, 0)
             - COALESCE(json_extract(m.raw_json, '$.return_commission.quantity'), 0)) * c.cost_price), 0)
        FROM monthly_realization_rows m
        LEFT JOIN ({_COST_LATEST}) c ON m.sku = c.sku
        WHERE m.month >= ? AND m.month < ?""", (m_from, m_to))

    cur.execute("SELECT DISTINCT month FROM monthly_realization_rows WHERE month >= ? AND month < ?", (m_from, m_to))
    closed_months = {r[0] for r in cur.fetchall()}

    # Открытые месяцы (ещё нет отчёта о реализации): realization_daily,
    # а если и его нет — оценка по начислениям accruals (1 строка POSTING с ценой = 1 шт).
    cogs_daily = 0.0
    cogs_estimated = False
    cur.execute("SELECT DISTINCT substr(date,1,7) FROM accruals WHERE date >= ? AND date < ?", rng)
    for (month,) in cur.fetchall():
        if month in closed_months:
            continue
        cur.execute("SELECT COUNT(*) FROM realization_daily WHERE substr(date,1,7) = ?", (month,))
        if (cur.fetchone() or [0])[0] > 0:
            cogs_daily += _one(cur, f"""
                SELECT COALESCE(SUM(CASE WHEN r.is_return THEN -1 ELSE 1 END * r.quantity * c.cost_price), 0)
                FROM realization_daily r
                LEFT JOIN ({_COST_LATEST}) c ON r.sku = c.sku
                WHERE substr(r.date,1,7) = ? AND r.date >= ? AND r.date < ?""", (month, date_from, date_to))
        else:
            cogs_estimated = True
            cogs_daily += _one(cur, f"""
                SELECT COALESCE(SUM(c.cost_price), 0)
                FROM accruals a LEFT JOIN ({_COST_LATEST}) c ON a.sku = c.sku
                WHERE a.accrued_category = 'POSTING' AND a.sale_price > 0
                  AND substr(a.date,1,7) = ? AND a.date >= ? AND a.date < ?""", (month, date_from, date_to))

    cogs = cogs_monthly + cogs_daily
    gross_profit = net_from_ozon - cogs
    margin_pct = (gross_profit / income * 100.0) if income > 0 else 0.0

    return {
        "date_from": date_from, "date_to": date_to,
        "income": income,
        "commission": commission,
        "services": services,
        "ozon_total": ozon_total,
        "net_from_ozon": net_from_ozon,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "margin_pct": margin_pct,
        "cogs_missing": income > 0 and cogs <= 0,
        "cogs_estimated": cogs_estimated,
    }


def year_range(year: int) -> tuple[str, str]:
    return f"{year}-01-01", f"{year + 1}-01-01"


def month_range(year: int, month: int) -> tuple[str, str]:
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{year}-{month:02d}-01", f"{ny}-{nm:02d}-01"


def receivables(cur) -> float:
    """Дебиторка Ozon. Приоритет — фактический баланс из balance_periods
    (цифра самого Ozon), иначе — расчёт начислено − выплачено."""
    try:
        cur.execute("SELECT end_balance FROM balance_periods WHERE end_balance IS NOT NULL ORDER BY period_end DESC LIMIT 1")
        row = cur.fetchone()
        if row and row[0] is not None:
            return float(row[0])
    except Exception as exc:  # noqa: BLE001
        log.debug("balance_periods недоступна: %s", exc)
    acc = _one(cur, "SELECT COALESCE(SUM(amount), 0) FROM finance_transactions", ())
    pay = _one(cur, "SELECT COALESCE(SUM(amount), 0) FROM finance_payouts", ())
    return acc - pay


def inventory_value(cur) -> float:
    """Остатки × последняя себестоимость — одна формула для Баланса, Пульта и Оборотного капитала."""
    cur.execute("SELECT MAX(date) FROM stock_daily")
    row = cur.fetchone()
    if not row or not row[0]:
        return 0.0
    return _one(cur, f"""
        SELECT COALESCE(SUM((s.fbo_present + s.fbs_present) * c.cost_price), 0)
        FROM stock_daily s LEFT JOIN ({_COST_LATEST}) c ON s.sku = c.sku
        WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0""", (row[0],))


REGIME_DR = "Д-Р"          # УСН «доходы − расходы»: налог = ставка × (Д − Р), минимум 1 % от доходов
REGIME_INCOME = "Доходы"   # УСН «доходы»: налог = ставка × доходы − взносы ИП (ИП без работников — до нуля)
DEFAULT_REGIME = REGIME_DR
DEFAULT_CONTRIB = 57390.0  # фиксированные взносы ИП за 2026 (ст. 430 НК; 2025 — 53 658)

# Лист НАСТРОЙКИ: B1 — ставка %, B4 — режим («доходы − расходы» / «доходы»), B5 — взносы ИП за год
SETTINGS_SHEET = "НАСТРОЙКИ"
SETTINGS_RATE, SETTINGS_REGIME, SETTINGS_CONTRIB = "B1", "B4", "B5"


def parse_regime(raw) -> str:
    """«доходы − расходы», «Д-Р», «15%» → Д-Р; «доходы», «6%» → Доходы; иначе DEFAULT_REGIME."""
    t = str(raw or "").lower().replace("−", "-").replace("–", "-").replace(" ", "")
    if not t:
        return DEFAULT_REGIME
    if "расход" in t or "д-р" in t or t in ("др", "15", "15%", "усн15"):
        return REGIME_DR
    if "доход" in t or t in ("6", "6%", "усн6", "д"):
        return REGIME_INCOME
    return DEFAULT_REGIME


def tax_settings(sh=None) -> dict:
    """Налоговые настройки из листа НАСТРОЙКИ: {rate_pct, regime, contrib}.
    Без доступа к таблице — значения по умолчанию (5 %, Д-Р, 57 390)."""
    out = {"rate_pct": DEFAULT_TAX_RATE_PCT, "regime": DEFAULT_REGIME, "contrib": DEFAULT_CONTRIB}
    if sh is None:
        return out
    try:
        ws = sh.worksheet(SETTINGS_SHEET)
        vals = ws.batch_get([SETTINGS_RATE, SETTINGS_REGIME, SETTINGS_CONTRIB])
        cell = lambda i: (vals[i][0][0] if vals[i] and vals[i][0] else "")  # noqa: E731
        raw = str(cell(0)).replace("%", "").replace(",", ".").strip()
        if raw:
            val = float(raw)
            if 0 < val < 100:
                out["rate_pct"] = val
        out["regime"] = parse_regime(cell(1))
        raw = str(cell(2)).replace("₽", "").replace(" ", "").replace("\xa0", "").replace(",", ".").strip()
        if raw:
            val = float(raw)
            if val >= 0:
                out["contrib"] = val
    except Exception as exc:  # noqa: BLE001
        log.warning("Лист НАСТРОЙКИ не прочитан (%s) — по умолчанию %s", exc, out)
    return out


def tax_rate_pct(sh=None) -> float:
    """Ставка налога, % (совместимость): НАСТРОЙКИ!B1 → иначе DEFAULT_TAX_RATE_PCT."""
    return tax_settings(sh)["rate_pct"]


if __name__ == "__main__":
    import sys
    from .db import connect

    year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    conn = connect()
    cur = conn.cursor()
    p = ozon_pnl(cur, *year_range(year))
    for k, v in p.items():
        print(f"{k:16} {v:>16,.2f}" if isinstance(v, float) else f"{k:16} {v}")
    print(f"{'receivables':16} {receivables(cur):>16,.2f}")
    print(f"{'inventory':16} {inventory_value(cur):>16,.2f}")
