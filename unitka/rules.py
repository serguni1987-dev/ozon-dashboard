"""unitka/rules.py — каталог управленческих правил для ПУЛЬТА.
Каждое правило — это функция, которая проверяет паспорт SKU и возвращает 
список задач (проблема, действие, эффект в рублях).
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Task:
    rule_id: str
    severity: int       # 1 = 🔴, 2 = 🟡, 3 = 🟢
    sku: str
    offer_id: str
    problem: str        # Что не так
    action: str         # Что делать
    money_impact: float # Эффект в рублях (потеря или выгода)


# Пороги правил. Значения по умолчанию; calc_action_plan подставляет значения с листа
# «НАСТРОЙКИ» (settings.rule_params), если там есть строки с такими подписями.
THRESHOLDS = {
    "dead_stock_days": 60,        # «Неликвид: дней без продаж»
    "negative_margin_pct": -5.0,  # «Убыточная маржа, %» (ниже этого значения — задача)
    "oos_lost_days": 7,           # за сколько дней простоя считать упущенную выручку
}


def _rub(v: float) -> str:
    """12825.4 → «12 825» (разряды через пробел, как принято в русских отчётах)."""
    return f"{v:,.0f}".replace(",", " ")


def set_thresholds(values: dict | None) -> None:
    """Обновляет пороги (только известные ключи с числовым значением)."""
    for key, val in (values or {}).items():
        if key in THRESHOLDS and isinstance(val, (int, float)):
            THRESHOLDS[key] = val


# Словарь с правилами. Функция принимает "паспорт" товара (dict) и возвращает Task или None.
# В будущем сюда легко добавить новые правила, не меняя сам calc_pulse.py.

def check_price_below_min(sku_data: dict) -> Optional[Task]:
    """Цена ниже минимальной (продаём в убыток)."""
    price = sku_data.get("price", 0)
    min_price = sku_data.get("min_price", 0)
    stock = sku_data.get("stock", 0)
    
    if stock > 0 and price > 0 and price < min_price:
        loss_per_unit = min_price - price
        total_loss = loss_per_unit * stock
        return Task(
            rule_id="price_below_min",
            severity=1,
            sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Цена {_rub(price)} ₽ ниже минимальной {_rub(min_price)} ₽",
            action=f"Поднять цену до {_rub(min_price)} ₽",
            money_impact=total_loss
        )
    return None


def check_out_of_stock(sku_data: dict) -> Optional[Task]:
    """Остаток 0, но товар продавался (упущенная выручка)."""
    stock = sku_data.get("stock", 0)
    sold_14d = sku_data.get("sold_14d", 0)
    avg_price = sku_data.get("avg_price", 0)
    
    if stock == 0 and sold_14d > 0:
        # Примерная упущенная выручка: продажи за 14 дней / 14 * N дней простоя * цену
        lost_revenue = (sold_14d / 14) * THRESHOLDS["oos_lost_days"] * avg_price
        return Task(
            rule_id="out_of_stock",
            severity=1,
            sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Нет в наличии, но было {sold_14d} продаж за 14 дней",
            action="Срочно пополнить остаток (FBO/FBS)",
            money_impact=lost_revenue
        )
    return None


def check_dead_stock(sku_data: dict, threshold_days: Optional[int] = None) -> Optional[Task]:
    """Неликвид (лежит на складе без продаж больше N дней)."""
    if threshold_days is None:
        threshold_days = THRESHOLDS["dead_stock_days"]
    stock = sku_data.get("stock", 0)
    days_no_sales = sku_data.get("days_no_sales", 0)
    cost_price = sku_data.get("cost", 0)
    
    if stock > 0 and days_no_sales >= threshold_days:
        frozen_capital = stock * cost_price
        return Task(
            rule_id="dead_stock",
            severity=2,
            sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Неликвид: {stock} шт лежат {days_no_sales} дней без продаж",
            action="Распродать (цена возврата денег) или вывести",
            money_impact=frozen_capital
        )
    return None


def check_negative_margin(sku_data: dict) -> Optional[Task]:
    """Отрицательная маржа (товар убыточен в целом)."""
    margin_pct = sku_data.get("margin_pct", 0)
    revenue_30d = sku_data.get("revenue_30d", 0)
    
    if margin_pct < THRESHOLDS["negative_margin_pct"] and revenue_30d > 0:  # порог отсекает случайные колебания
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
            rule_id="negative_margin",
            severity=1,
            sku=sku_data["sku"],
            offer_id=sku_data.get("offer_id", ""),
            problem=f"Маржинальность {margin_pct:.1f}% (убыток {_rub(loss)} ₽ за 30 дней)",
            action=action,
            money_impact=loss
        )
    return None


# Единый список всех правил
ALL_RULES = [
    check_price_below_min,
    check_out_of_stock,
    check_dead_stock,
    check_negative_margin,
]


def evaluate_sku(sku_data: dict) -> List[Task]:
    """Применяет все правила к одному SKU и возвращает список задач."""
    tasks = []
    for rule_func in ALL_RULES:
        result = rule_func(sku_data)
        if result:
            tasks.append(result)
    return tasks