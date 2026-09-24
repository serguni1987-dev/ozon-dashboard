src = open("pnl_format.py", encoding="utf-8").read()

# 1) Формат ROI: 0% → 0.00" %"
old = '''    reqs.append({"repeatCell": {
        "range": grid(sid, 43, 44, 1, 19),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": '0%'}}},
        "fields": "userEnteredFormat.numberFormat"}})'''
new = '''    reqs.append({"repeatCell": {
        "range": grid(sid, 43, 44, 1, 19),
        "cell": {"userEnteredFormat": {"numberFormat": {
            "type": "NUMBER", "pattern": '0.00" %"'}}},
        "fields": "userEnteredFormat.numberFormat"}})'''
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] Формат ROI обновлён на 0.00\" %\"")
else:
    print("[i] Формат ROI уже обновлён или не найден")

# 2) Примечания для 33-37 (перезапишем только эти ключи)
old_notes = {
    33: "Постоянные расходы: персонал, админ, коммерческие.",
    34: "Зарплата, налоги с ФОТ.",
    35: "Аренда, связь, канцелярия.",
    36: "Реклама вне Ozon, упаковка.",
    37: "Прочие операционные расходы.",
}
new_notes = {
    33: "Считается автоматически: = СУММА строк 34–37. Вручную не редактировать.",
    34: "Внести вручную (по месяцам C..N). Год и кварталы посчитаются сами.",
    35: "Внести вручную (по месяцам C..N). Год и кварталы посчитаются сами.",
    36: "Внести вручную (по месяцам C..N). Год и кварталы посчитаются сами.",
    37: "Внести вручную (по месяцам C..N). Год и кварталы посчитаются сами.",
}
for r, old_txt in old_notes.items():
    if old_txt in src:
        src = src.replace(old_txt, new_notes[r], 1)
        print(f"[OK] Примечание к строке {r} обновлено")
    else:
        print(f"[i] Примечание к строке {r} не найдено (пропускаю)")

open("pnl_format.py", "w", encoding="utf-8").write(src)
print("[OK] pnl_format.py сохранён")
