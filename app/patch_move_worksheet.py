src = open("sheets_sync.py", encoding="utf-8").read()

old = '''    # Перемещаем в начало списка вкладок
    try:
        sh.move_worksheet(ws, 0)
        print("  Перемещён на первое место")
    except Exception as e:
        print(f"  [WARN] Не удалось переместить: {e}")'''

new = '''    # Перемещаем в начало списка вкладок через API
    try:
        sh.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "index": 0},
                "fields": "index",
            }
        }]})
        print("  Перемещён на первое место")
    except Exception as e:
        print(f"  [WARN] Не удалось переместить: {e}")'''

if old in src:
    src = src.replace(old, new)
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] sync_manual: move_worksheet -> batch_update")
else:
    print("[?] Не нашёл блок перемещения")
