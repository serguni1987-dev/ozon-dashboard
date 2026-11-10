import inspect
from unitka import db

print("=== Функции и классы в unitka.db ===")
for name, obj in inspect.getmembers(db):
    if not name.startswith('__'):
        if inspect.isfunction(obj):
            print(f"Функция: {name}{inspect.signature(obj)}")
        elif inspect.isclass(obj):
            print(f"Класс: {name}")
        elif name.isupper():
            print(f"Константа: {name}")