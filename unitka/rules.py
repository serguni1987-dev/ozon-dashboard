"""Management rules. Out-of-stock demand alone never authorizes purchasing."""
from dataclasses import dataclass
import math
from typing import List, Optional


@dataclass
class Task:
    rule_id: str
    severity: int
    sku: str
    offer_id: str
    problem: str
    action: str
    money_impact: float


DEFAULT_THRESHOLDS = {
    "dead_stock_days": 60,
    "negative_margin_pct": -5.0,
    "oos_lost_days": 7,
}
THRESHOLDS = dict(DEFAULT_THRESHOLDS)


def _rub(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def _finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def set_thresholds(values: dict | None) -> None:
    """Each calculation starts from defaults; invalid overrides are ignored."""
    THRESHOLDS.clear()
    THRESHOLDS.update(DEFAULT_THRESHOLDS)
    for key, value in (values or {}).items():
        if key not in DEFAULT_THRESHOLDS or not isinstance(value, (int, float)):
            continue
        number = _finite(value)
        if number is None:
            continue
        if key == "negative_margin_pct":
            if number <= 0:
                THRESHOLDS[key] = number
        elif number > 0:
            THRESHOLDS[key] = number


def check_price_below_min(sku_data: dict) -> Optional[Task]:
    """Existing price-gap rule; monetary interpretation is audited separately."""
    price = sku_data.get("price", 0)
    min_price = sku_data.get("min_price", 0)
    stock = sku_data.get("stock", 0)
    if stock > 0 and price > 0 and price < min_price:
        loss_per_unit = min_price - price
        total_loss = loss_per_unit * stock
        return Task(
            rule_id="price_below_min", severity=1, sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Цена {_rub(price)} ₽ ниже минимальной {_rub(min_price)} ₽",
            action=f"Поднять цену до {_rub(min_price)} ₽", money_impact=total_loss)
    return None


def check_out_of_stock(sku_data: dict) -> Optional[Task]:
    """Demand estimate, not a verified loss or unconditional purchase order."""
    stock = _finite(sku_data.get("stock"))
    sold = _finite(sku_data.get("sold_14d"))
    if stock != 0 or sold is None or sold <= 0:
        return None
    average = _finite(sku_data.get("avg_price"))
    estimated_revenue = sold / 14 * THRESHOLDS["oos_lost_days"] * average if average is not None and average > 0 else 0.0
    if not math.isfinite(estimated_revenue):
        estimated_revenue = 0.0
    cost = _finite(sku_data.get("cost"))
    floor = _finite(sku_data.get("min_price"))
    price = _finite(sku_data.get("price"))
    margin = _finite(sku_data.get("margin_pct"))
    revenue = _finite(sku_data.get("revenue_30d"))
    known = (cost is not None and cost > 0 and floor is not None and floor > 0
             and price is not None and price > 0 and margin is not None
             and revenue is not None and revenue > 0)
    if not known:
        action = "Сначала проверить себестоимость, цены и расходы; данных для рекомендации закупки недостаточно"
    elif margin <= 0 or price < floor:
        action = "Сначала проверить и исправить экономику товара; пополнение пока не рекомендовано"
    else:
        action = "Рассмотреть пополнение только после проверки полной прибыли, оборачиваемости и бюджета"
    return Task(
        rule_id="out_of_stock", severity=2, sku=sku_data["sku"],
        offer_id=sku_data.get("offer_id", ""),
        problem=f"Нет в наличии, но было {sold:g} продаж за 14 дней; упущенная выручка — оценка",
        action=action, money_impact=estimated_revenue)


def check_dead_stock(sku_data: dict, threshold_days: Optional[int] = None) -> Optional[Task]:
    if threshold_days is None:
        threshold_days = THRESHOLDS["dead_stock_days"]
    stock = sku_data.get("stock", 0)
    days_no_sales = sku_data.get("days_no_sales", 0)
    cost_price = sku_data.get("cost", 0)
    if stock > 0 and days_no_sales >= threshold_days:
        frozen_capital = stock * cost_price
        return Task(
            rule_id="dead_stock", severity=2, sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Неликвид: {stock} шт лежат {days_no_sales} дней без продаж",
            action="Распродать (цена возврата денег) или вывести", money_impact=frozen_capital)
    return None


def check_negative_margin(sku_data: dict) -> Optional[Task]:
    margin_pct = sku_data.get("margin_pct", 0)
    revenue_30d = sku_data.get("revenue_30d", 0)
    if margin_pct < THRESHOLDS["negative_margin_pct"] and revenue_30d > 0:
        loss = abs(revenue_30d * (margin_pct / 100))
        price = sku_data.get("price", 0)
        min_price = sku_data.get("min_price", 0)
        if min_price > 0 and 0 < price < min_price:
            action = f"Поднять цену до {_rub(min_price)} ₽ (сейчас {_rub(price)} ₽)"
        elif min_price > 0 and price >= min_price:
            action = (f"Цена {_rub(price)} ₽ уже выше минимальной {_rub(min_price)} ₽ — "
                      "проверить акции и возвраты за 30 дней")
        else:
            action = "Поднять цену или отключить товар"
        return Task(
            rule_id="negative_margin", severity=1, sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Маржинальность {margin_pct:.1f}% (убыток {_rub(loss)} ₽ за 30 дней)",
            action=action, money_impact=loss)
    return None


ALL_RULES = [check_price_below_min, check_out_of_stock, check_dead_stock, check_negative_margin]


def evaluate_sku(sku_data: dict) -> List[Task]:
    tasks = []
    for rule_func in ALL_RULES:
        result = rule_func(sku_data)
        if result:
            tasks.append(result)
    return tasks
