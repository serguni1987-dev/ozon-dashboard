"""unitka/unit_core.py — экономика по SKU и минимальная цена (точка безубыточности).

Зачем: до 2026-11-10 «Юнит-сводка» и блок «Убыточные SKU» в Пульте считали
    выручка − себестоимость − расходы
по таблице realization_daily, где на каждое начисление (в т.ч. услуги) своя строка
с quantity = 1. Штуки и себестоимость завышались в 2–3 раза, комиссия Ozon не
учитывалась вовсе, а «мин. цена» была суммой расходов за год × 1,15.
Здесь — один расчёт, который сходится с P&L (finance_core.ozon_pnl) до рубля.

Источники (только чтение БД):
    штуки, доходы, комиссия   закрытые месяцы — monthly_realization_rows (отчёт о реализации),
                              открытый месяц — accruals (строка POSTING с ценой = 1 шт)
    услуги по SKU             accruals_services со SKU (логистика, эквайринг, возвраты …)
    общие расходы Ozon        всё остальное, что удержал Ozon (реклама, подписки, штрафы,
                              баллы за отзывы) — распределяются по SKU пропорционально доходу
    себестоимость             product_cost_history (последняя цена закупки)
    тариф комиссии, цена      current_prices (app/fetch_current_prices.py)

Минимальная цена (цена продавца, с которой Ozon считает комиссию):

    мин. цена = (себестоимость + фикс. расходы Ozon на 1 шт)
                / (1 − комиссия% − эквайринг и пр.% − налог% [− общие расходы%] [− целевая маржа%])

    «в ноль»            без общих расходов: ниже этой цены каждая продажа — прямой убыток
    «с общими расходами» + реклама, подписки, штрафы: ниже — магазин в целом в минусе
    «целевая»           + целевая маржа из НАСТРОЕК

Фикс. расходы на 1 шт включают логистику отмен и возвратов (они делятся на
выкупленные штуки), поэтому товар с частыми отменами получает более высокую мин. цену.
Налог: при УСН «доходы − расходы» в точке безубыточности платится минимальный
налог 1 % от доходов; при УСН «доходы» — ставка целиком.
"""
from __future__ import annotations

import json
import logging

from .finance_core import (
    DEFAULT_TAX_RATE_PCT, REGIME_DR, _COST_LATEST, _month_bounds, ozon_pnl,
)

log = logging.getLogger(__name__)

# Услуги, которые берутся процентом от цены (остальные услуги со SKU считаем фиксом на штуку)
PCT_SERVICE_TYPES = {1, 3, 74}       # Acquiring, BrandCommission, StarsMembership
MIN_UNITS_FOR_OWN_RATE = 3           # меньше — фикс. расходы на штуку берём средние по магазину
MIN_DENOMINATOR = 0.10               # если на покрытие остаётся < 10 % цены — цена недостижима
MIN_TAX_PCT_DR = 1.0                 # минимальный налог УСН Д−Р, % от доходов


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _blank(sku) -> dict:
    return {
        "sku": sku, "offer_id": "", "name": "",
        "delivered": 0.0, "returned": 0.0, "units": 0.0,
        "income": 0.0, "commission": 0.0,
        "svc_fixed": 0.0, "svc_pct": 0.0,
        "cost_unit": 0.0, "cogs": 0.0, "stock": 0,
    }


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def sku_economics(cur, date_from: str, date_to: str) -> dict:
    """Экономика по SKU за [date_from, date_to). Возвращает {"skus": {sku: {...}}, "totals": {...}}.

    Σ по SKU сходится с finance_core.ozon_pnl: доходы, себестоимость и валовая прибыль
    (общие расходы Ozon = всё удержанное минус комиссия и услуги со SKU).
    """
    skus: dict = {}

    def get(sku):
        try:
            sku = int(sku)
        except (TypeError, ValueError):
            pass
        if sku not in skus:
            skus[sku] = _blank(sku)
        return skus[sku]

    # --- 1. Закрытые месяцы: отчёт о реализации (штуки, доходы, комиссия) ---
    closed = []
    cur.execute("SELECT DISTINCT month FROM monthly_realization_rows")
    have = {r[0] for r in cur.fetchall()}
    for month, _start, _end in _month_bounds(date_from, date_to):
        if month in have:
            closed.append(month)
    money_keys = ("amount", "bonus", "bank_coinvestment", "pick_up_point_coinvestment")
    for month in closed:
        cur.execute("SELECT sku, offer_id, item_name, quantity, raw_json FROM monthly_realization_rows WHERE month = ?", (month,))
        for sku, offer_id, name, qty, raw in cur.fetchall():
            s = get(sku)
            s["offer_id"] = s["offer_id"] or (offer_id or "")
            s["name"] = s["name"] or (name or "")
            try:
                j = json.loads(raw) if raw else {}
            except (TypeError, ValueError):
                j = {}
            dc = j.get("delivery_commission") or {}
            rc = j.get("return_commission") or {}
            s["delivered"] += _f(dc.get("quantity")) if dc else _f(qty)
            s["returned"] += _f(rc.get("quantity"))
            s["income"] += sum(_f(dc.get(k)) for k in money_keys) - sum(_f(rc.get(k)) for k in money_keys)
            s["commission"] += _f(dc.get("standard_fee")) - _f(rc.get("standard_fee"))

    # --- 2. Остальные дни периода: начисления accruals (строка POSTING с ценой = 1 шт) ---
    not_closed = ("AND substr(date,1,7) NOT IN (%s)" % ",".join("?" * len(closed))) if closed else ""
    cur.execute(f"""
        SELECT sku, sale_price, bonus, coinvestment, sale_commission
        FROM accruals
        WHERE accrued_category = 'POSTING' AND COALESCE(sale_price, 0) != 0
          AND date >= ? AND date < ? {not_closed}""", (date_from, date_to, *closed))
    for sku, price, bonus, coinv, comm in cur.fetchall():
        s = get(sku)
        if _f(price) > 0:
            s["delivered"] += 1
        else:
            s["returned"] += 1
        s["income"] += _f(price) + _f(bonus) + _f(coinv)
        s["commission"] += -_f(comm)          # в accruals комиссия со знаком минус, у возврата — плюс

    # --- 3. Услуги Ozon, привязанные к SKU ---
    cur.execute("""
        SELECT sku, type_id, SUM(amount) FROM accruals_services
        WHERE sku IS NOT NULL AND sku != '' AND sku != 0 AND date >= ? AND date < ?
        GROUP BY sku, type_id""", (date_from, date_to))
    for sku, type_id, amount in cur.fetchall():
        s = get(sku)
        key = "svc_pct" if type_id in PCT_SERVICE_TYPES else "svc_fixed"
        s[key] += -_f(amount)                 # расход хранится со знаком минус

    # --- 4. Себестоимость, артикулы, остатки ---
    cur.execute(_COST_LATEST)
    cost = {}
    for sku, price in cur.fetchall():
        try:
            cost[int(sku)] = _f(price)
        except (TypeError, ValueError):
            cost[sku] = _f(price)
    offers = {}
    try:
        cur.execute("SELECT sku, offer_id, name FROM products WHERE offer_id IS NOT NULL AND offer_id != ''")
        for sku, offer_id, name in cur.fetchall():
            try:
                offers[int(sku)] = (offer_id, name or "")
            except (TypeError, ValueError):
                continue
    except Exception as exc:  # noqa: BLE001
        log.debug("products недоступна: %s", exc)
    stock = {}
    try:
        cur.execute("SELECT MAX(date) FROM stock_daily")
        last = (cur.fetchone() or [None])[0]
        if last:
            cur.execute("SELECT sku, fbo_present + fbs_present FROM stock_daily WHERE date = ? AND fbo_present + fbs_present > 0", (last,))
            for sku, qty in cur.fetchall():
                try:
                    stock[int(sku)] = int(_f(qty))
                except (TypeError, ValueError):
                    continue
    except Exception as exc:  # noqa: BLE001
        log.debug("stock_daily недоступна: %s", exc)

    for sku in set(stock) - set(skus):        # товар на складе без продаж — тоже нужна мин. цена
        get(sku)
    for sku, s in skus.items():
        s["units"] = s["delivered"] - s["returned"]
        s["cost_unit"] = cost.get(sku, 0.0)
        s["cogs"] = s["units"] * s["cost_unit"]
        s["stock"] = stock.get(sku, 0)
        if sku in offers:
            s["offer_id"] = s["offer_id"] or offers[sku][0]
            s["name"] = s["name"] or offers[sku][1]

    # --- 5. Итоги и общие расходы Ozon (сверка с P&L) ---
    pnl = ozon_pnl(cur, date_from, date_to)
    t = {k: sum(s[k] for s in skus.values()) for k in
         ("delivered", "returned", "units", "income", "commission", "svc_fixed", "svc_pct", "cogs")}
    t["svc_sku"] = t["svc_fixed"] + t["svc_pct"]
    t["overhead"] = pnl["ozon_total"] - t["commission"] - t["svc_sku"]
    t["ozon_total"] = pnl["ozon_total"]
    t["gross_profit"] = t["income"] - t["commission"] - t["svc_sku"] - t["overhead"] - t["cogs"]
    t["pnl_income"], t["pnl_cogs"], t["pnl_gross_profit"] = pnl["income"], pnl["cogs"], pnl["gross_profit"]
    inc = t["income"]
    t["commission_pct"] = t["commission"] / inc * 100 if inc > 0 else 0.0
    t["svc_pct_pct"] = t["svc_pct"] / inc * 100 if inc > 0 else 0.0
    t["overhead_pct"] = t["overhead"] / inc * 100 if inc > 0 else 0.0
    t["fixed_per_unit"] = t["svc_fixed"] / t["units"] if t["units"] > 0 else 0.0
    t["margin_pct"] = t["gross_profit"] / inc * 100 if inc > 0 else 0.0
    t["closed_months"], t["cogs_estimated"] = closed, pnl["cogs_estimated"]

    for s in skus.values():
        s["overhead"] = t["overhead"] * s["income"] / inc if inc > 0 else 0.0
        s["direct_profit"] = s["income"] - s["commission"] - s["svc_fixed"] - s["svc_pct"] - s["cogs"]
        s["profit"] = s["direct_profit"] - s["overhead"]
        s["margin_pct"] = s["profit"] / s["income"] * 100 if s["income"] > 0 else 0.0
    return {"skus": skus, "totals": t, "date_from": date_from, "date_to": date_to}


def load_prices(cur) -> dict:
    """Текущие цены и тарифы из current_prices: {sku: {price, tariff_pct, fetched_at}}."""
    out = {}
    if not _table_exists(cur, "current_prices"):
        return out
    try:
        cur.execute("""
            SELECT p.sku, cp.price, cp.marketing_price, cp.sales_percent_fbs, cp.sales_percent_fbo, cp.fetched_at
            FROM current_prices cp JOIN products p ON p.offer_id = cp.offer_id""")
        for sku, price, mprice, fbs, fbo, fetched in cur.fetchall():
            try:
                sku = int(sku)
            except (TypeError, ValueError):
                continue
            cur_price = _f(mprice) or _f(price)
            tariff = max(_f(fbs), _f(fbo))
            out[sku] = {"price": cur_price, "tariff_pct": tariff, "fetched_at": fetched or ""}
    except Exception as exc:  # noqa: BLE001
        log.warning("current_prices не прочитана: %s", exc)
    return out


def price_floor(cost_unit: float, fixed_unit: float, rates_pct: float):
    """Цена, при которой (цена × (1 − rates) − фикс − себестоимость) = 0. None — недостижимо."""
    denom = 1.0 - rates_pct / 100.0
    if cost_unit <= 0 or denom < MIN_DENOMINATOR:
        return None
    return (cost_unit + fixed_unit) / denom


def min_prices(cur, eco: dict, tax: dict | None = None, unit: dict | None = None) -> dict:
    """Минимальные цены по SKU. tax — finance_core.tax_settings(), unit — settings.unit_params().

    Возвращает {sku: {commission_pct, fixed_unit, rates_pct, min_direct, min_full, target,
    price, headroom_pct, status, basis}} и кладёт параметры расчёта в eco["totals"]["price_params"].
    """
    tax = tax or {"rate_pct": DEFAULT_TAX_RATE_PCT, "regime": REGIME_DR}
    unit = unit or {"target_margin_pct": 20.0, "overhead_pct": None}
    t = eco["totals"]
    tax_pct = MIN_TAX_PCT_DR if tax.get("regime") == REGIME_DR else _f(tax.get("rate_pct"))
    overhead_pct = unit["overhead_pct"] if unit.get("overhead_pct") is not None else max(0.0, t["overhead_pct"])
    target_pct = _f(unit.get("target_margin_pct"))
    other_pct = max(0.0, t["svc_pct_pct"])
    prices = load_prices(cur)
    t["price_params"] = {
        "tax_pct": tax_pct, "overhead_pct": overhead_pct, "target_margin_pct": target_pct,
        "other_pct": other_pct, "store_commission_pct": t["commission_pct"],
        "store_fixed_per_unit": t["fixed_per_unit"],
        "prices_fetched_at": max((p["fetched_at"] for p in prices.values()), default=""),
    }

    out = {}
    for sku, s in eco["skus"].items():
        p = prices.get(sku, {})
        basis = []
        if p.get("tariff_pct", 0) > 0:
            comm_pct = p["tariff_pct"]                      # действующий тариф Ozon
        elif s["income"] > 0 and s["commission"] > 0:
            comm_pct = s["commission"] / s["income"] * 100  # факт по SKU
            basis.append("комиссия — факт SKU")
        else:
            comm_pct = t["commission_pct"]
            basis.append("комиссия — средняя")
        if s["units"] >= MIN_UNITS_FOR_OWN_RATE:
            fixed_unit = max(0.0, s["svc_fixed"]) / s["units"]
        else:
            fixed_unit = t["fixed_per_unit"]
            basis.append("логистика — средняя")
        direct = comm_pct + other_pct + tax_pct
        rec = {
            "commission_pct": comm_pct, "fixed_unit": fixed_unit, "rates_pct": direct,
            "min_direct": price_floor(s["cost_unit"], fixed_unit, direct),
            "min_full": price_floor(s["cost_unit"], fixed_unit, direct + overhead_pct),
            "target": price_floor(s["cost_unit"], fixed_unit, direct + overhead_pct + target_pct),
            "price": p.get("price", 0.0), "headroom_pct": None,
            "basis": "; ".join(basis),
        }
        price = rec["price"]
        if s["cost_unit"] <= 0:
            rec["status"] = "⚪ нет себестоимости"
        elif rec["min_direct"] is None:
            rec["status"] = "🔴 при текущих тарифах в ноль не выйти"
        elif price <= 0:
            rec["status"] = "⚪ нет текущей цены"
        else:
            rec["headroom_pct"] = (price - rec["min_direct"]) / price * 100   # запас до «мин. цены в ноль»
            if price < rec["min_direct"]:
                rec["status"] = "🔴 ниже мин. цены — продажа в убыток"
            elif rec["min_full"] is None or price < rec["min_full"]:
                rec["status"] = "🟡 не покрывает рекламу и общие расходы"
            elif rec["target"] is None or price < rec["target"]:
                rec["status"] = "🟡 ниже целевой маржи"
            else:
                rec["status"] = "🟢 цена в норме"
        out[sku] = rec
    return out


def price_alerts(cur, tax: dict | None = None, unit: dict | None = None, year: int | None = None) -> dict:
    """Сводка для Пульта: товары на складе, цена которых ниже минимальной.

    {"below": [...], "thin": [...], "loss_per_stock": ₽, "params": {...}}
    below — цена ниже «мин. цены в ноль» (каждая продажа — прямой убыток),
    thin  — цена не покрывает рекламу и общие расходы Ozon.
    """
    from datetime import date as _date
    y = year or _date.today().year
    eco = sku_economics(cur, f"{y}-01-01", f"{y + 1}-01-01")
    mp = min_prices(cur, eco, tax, unit)
    below, thin = [], []
    below_all = {}   # артикул → (цена, мин. цена) для всех товаров, не только тех, что на складе
    for sku, s in eco["skus"].items():
        m = mp[sku]
        if m["price"] > 0 and m["min_direct"] is not None and m["price"] < m["min_direct"]:
            below_all[s["offer_id"] or str(sku)] = (m["price"], m["min_direct"])
        if s["stock"] <= 0 or m["price"] <= 0 or m["min_direct"] is None:
            continue
        rec = {"sku": sku, "offer_id": s["offer_id"] or str(sku), "stock": s["stock"],
               "price": m["price"], "min_direct": m["min_direct"], "min_full": m["min_full"]}
        if m["price"] < m["min_direct"]:
            rec["loss"] = (m["min_direct"] - m["price"]) * s["stock"]
            below.append(rec)
        elif m["min_full"] is None or m["price"] < m["min_full"]:
            thin.append(rec)
    below.sort(key=lambda r: -r["loss"])
    return {"below": below, "thin": thin, "below_all": below_all,
            "loss_per_stock": sum(r["loss"] for r in below),
            "params": eco["totals"]["price_params"], "totals": eco["totals"]}
