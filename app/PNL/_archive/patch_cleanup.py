import re
src = open("cleanup_dead.py", encoding="utf-8").read()

old = re.compile(
    r"def classify\(row\):.*?return \(\"low_traffic\", \"мало показов\",\n                \"Проверить рекламу, акции, бустинг\"\)\n",
    re.DOTALL
)

new = '''def classify(r):
    """Возвращает (reason_code, reason_text, action_text)."""
    views = r["views"] or 0
    pdp = r["pdp"] or 0
    pos = r["pos"]
    price_idx = r["price_idx"]
    stock = r["stock"]
    discount = r["discount"]

    # stock может прийти строкой — приводим к int
    try:
        stock_val = int(stock) if stock is not None else None
    except (TypeError, ValueError):
        stock_val = None

    # Нет остатка — нечего продавать
    if stock_val is not None and stock_val <= 0:
        return ("out_of_stock", "нет остатка",
                "Заказать или скрыть из выдачи")

    # Плохая позиция в поиске
    if pos is None or (isinstance(pos, int) and pos > 50):
        return ("poor_position", "низкая позиция",
                "Оптимизировать SEO-название, ключи")

    # Цена выше рынка
    if price_idx and any(s in str(price_idx).lower() for s in ["дорог", "очень дорог"]):
        return ("price_issue", f"цена: {price_idx}",
                "Снизить цену или обосновать в описании")

    # Трафик есть, но до карточки не доходят
    if views >= 300 and pdp == 0:
        return ("no_pdp", "не доходят до карточки",
                "Улучшить главное фото / заголовок")

    if views >= 300:
        return ("low_conv", "трафик есть, конверсии нет",
                "Изменить фото, описание, цену; добавить отзывы")

    # Мало показов — тест
    return ("low_traffic", "мало показов",
            "Проверить рекламу, акции, бустинг")
'''

src2, n = old.subn(new, src)
print(f"Патч classify: {'OK' if n else 'НЕ НАЙДЕН'}")

if n:
    open("cleanup_dead.py", "w", encoding="utf-8").write(src2)
    print("Файл обновлён. Запускайте: py cleanup_dead.py")
else:
    print("Не удалось найти функцию classify — пришлите файл целиком.")
