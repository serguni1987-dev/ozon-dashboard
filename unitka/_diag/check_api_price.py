from unitka.ozon_client import OzonClient
from unitka import config
import json

client = OzonClient()

# Проверяем OCP013E4
sku = "1288893361"
print(f"Запрашиваем цену для SKU {sku}...")

try:
    # Используем метод v4 для получения информации о ценах
    payload = {"sku": [int(sku)]}
    data = client._post("/v4/product/info/prices", payload)
    
    items = data.get("items", [])
    if items:
        item = items[0]
        print("\n=== РЕАЛЬНЫЕ ДАННЫЕ ИЗ OZON ===")
        print(f"Цена: {item.get('price', {}).get('price')} ₽")
        print(f"Цена со скидкой: {item.get('price', {}).get('marketing_price')} ₽")
        print(f"Мин. цена для акций: {item.get('price', {}).get('min_price')} ₽")
    else:
        print("Товар не найден в Ozon API.")
except Exception as e:
    print(f"Ошибка API: {e}")