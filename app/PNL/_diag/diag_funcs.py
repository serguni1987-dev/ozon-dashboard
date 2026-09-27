src = open("sheets_sync.py", encoding="utf-8").read()
funcs = ["build_prices", "format_prices", "sync_prices",
         "build_frozen", "format_frozen", "sync_frozen",
         "sync_money", "format_money",
         "sync_result", "format_result",
         "build_money", "build_result",
         "sync_today", "format_today",
         "sync_actions", "format_actions",
         "main"]
print("Что есть в файле:")
for f in funcs:
    mark = "OK" if f"def {f}" in src else "MISSING"
    print(f"  {f:<20} {mark}")
print(f"\nВсего строк: {len(src.splitlines())}")
print(f"Есть __main__: {'__main__' in src}")
