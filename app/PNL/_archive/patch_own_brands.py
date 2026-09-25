src = open("mark_brands.py", encoding="utf-8").read()

OLD = '''OWN_BRANDS = [
    'VIVA - HOME TEXTILE',
    'VIVA HOME TEXTILE',
]'''

NEW = '''OWN_BRANDS = [
    'VIVA - HOME TEXTILE',
    'VIVA HOME TEXTILE',
    'VIVA-HOME TEXTILE',
    'VIVA-HOME-TEXTILE',
]'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Добавлены варианты бренда с дефисом")
else:
    print("[?] Не нашёл OWN_BRANDS")

open("mark_brands.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")