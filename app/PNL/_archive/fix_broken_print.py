src = open("sheets_sync.py", encoding="utf-8").read()

# Битый блок
old = '''def sync_result(sh, con):
    print("
[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")'''

# Правильный
new = '''def sync_result(sh, con):
    print("\\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")'''

if old in src:
    src = src.replace(old, new)
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] Строка исправлена")
else:
    print("[?] Не нашёл. Смотрю другие варианты...")
    # Альтернативный вариант: \\n превратился в реальный перенос
    old2 = 'def sync_result(sh, con):\n    print("\n[Лист РЕЗУЛЬТАТ]")\n    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")'
    if old2 in src:
        src = src.replace(old2, new)
        open("sheets_sync.py", "w", encoding="utf-8").write(src)
        print("[OK] Строка исправлена (вариант 2)")
    else:
        # Ищем любые похожие поломки print("\n
        import re
        pattern = re.compile(r'print\("\n(\[[^\]]+\]")')
        matches = pattern.findall(src)
        print(f"[i] Найдено ещё битых print: {len(matches)}")
        for m in matches:
            print(f"  → {m}")
        # Исправляем все
        src = pattern.sub(r'print("\\n\1', src)
        open("sheets_sync.py", "w", encoding="utf-8").write(src)
        print("[OK] Все битые print исправлены")
