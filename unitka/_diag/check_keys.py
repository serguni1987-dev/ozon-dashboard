import os
from unitka import config

print("=== Проверка ключей ===")
print(f"config.OZON_CLIENT_ID: {'ЕСТЬ' if config.OZON_CLIENT_ID else 'ПУСТО'}")
print(f"config.OZON_API_KEY:   {'ЕСТЬ' if config.OZON_API_KEY else 'ПУСТО'}")
print(f"os.getenv('OZON_CLIENT_ID'): {'ЕСТЬ' if os.getenv('OZON_CLIENT_ID') else 'ПУСТО (None)'}")
print(f"os.getenv('OZON_API_KEY'):   {'ЕСТЬ' if os.getenv('OZON_API_KEY') else 'ПУСТО (None)'}")