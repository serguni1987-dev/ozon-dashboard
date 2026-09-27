src = open("sheets_sync.py", encoding="utf-8").read()

if "def sync_manual" in src:
    print("[i] sync_manual уже есть")
    exit(0)

new_code = '''
# ============ ЛИСТ ИНСТРУКЦИЯ ============
def build_manual(con):
    data = [
        ["ПУЛЬТ OZON — ИНСТРУКЦИЯ", "", ""],
        ["", "", ""],
        ["🚀 ЕЖЕДНЕВНЫЙ РИТУАЛ  (5-15 минут утром)", "", ""],
        ["1.", "Скачать свежий .xlsx из ЛК Ozon", ""],
        ["", "Аналитика → Отчёты → Аналитика по товарам", ""],
        ["", "Период: последние 30 дней", ""],
        ["", "Положить в папку downloads/", ""],
        ["2.", "Включить VPN (Windscribe)", ""],
        ["", "Без VPN Google Sheets не обновится", ""],
        ["3.", "Запустить пульт", ""],
        ["", "py run.py   или двойной клик run.bat", ""],
        ["4.", "Открыть Google Sheets", ""],
        ["", "6 листов обновятся автоматически", ""],
        ["5.", "Выбрать 3 действия на сегодня", ""],
        ["", "Одно по ценам, одно по карточкам, одно по заморозке", ""],
        ["", "Отметить «да» в колонке «Сделано?» на листе ДЕЛАЙ", ""],
        ["", "", ""],
        ["📊 ЧТО ОЗНАЧАЕТ КАЖДЫЙ ЛИСТ", "", ""],
        ["СЕГОДНЯ", "Что происходит. Вердикт дня, топ-3, куда смотреть", ""],
        ["ДЕЛАЙ", "Что делать. 57 SKU, эффект в ₽/мес, отсортировано по деньгам", ""],
        ["ЦЕНЫ", "42 SKU с остатком. Индекс RED/SUPER, рекомендации ↓/↑", ""],
        ["ЗАМОРОЗКА", "Где деньги. 171k ₽ в складе, 30 мёртвых, что высвободить", ""],
        ["ДЕНЬГИ", "Сколько заработал. 7д / 30д / с 1 августа + по месяцам", ""],
        ["РЕЗУЛЬТАТ", "Динамика. Δ к прошлому запуску, автоматические выводы", ""],
        ["", "", ""],
        ["📅 ПЛАН НА МЕСЯЦ", "", ""],
        ["Неделя 1", "Цены: поднять SUPER (12 SKU), закрыть убыточные (11 SKU). Эффект: +15 500 ₽/мес", ""],
        ["Неделя 2", "Заморозка: топ-15 мёртвых SKU = 78 000 ₽. Освободить ~50 000 ₽", ""],
        ["Неделя 3", "Карточки: переделать 14 SKU (фото, описание, видео). Эффект: +18 855 ₽/мес", ""],
        ["Неделя 4", "Доставка: проверить 15 SKU с брошенными корзинами. Эффект: до 122 000 ₽/мес", ""],
        ["", "", ""],
        ["🔧 ЕСЛИ ЧТО-ТО СЛОМАЛОСЬ", "", ""],
        ["Google Sheets", "Проверь VPN. py check_google.py → должен быть Google API: 200", ""],
        ["Ошибка в run.py", "Запусти проблемный скрипт отдельно: py <название>.py", ""],
        ["Данные не идут", "Проверь downloads/ — есть ли свежий .xlsx", ""],
        ["Восстановить базу", "copy backups/ozon_<дата>.db ozon.db", ""],
        ["", "", ""],
        ["⚙️ ТЕХНИЧЕСКИЕ ДЕТАЛИ", "", ""],
        ["Папка проекта", "C:/Users/sergu/Desktop/проект/", ""],
        ["Главный скрипт", "run.py — утренний ритуал (11 шагов)", ""],
        ["База данных", "ozon.db — вся история продаж, цен, остатков", ""],
        ["Google Sheet ID", "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0", ""],
        ["Service Account", "ozon-bot@ozon-dashboard-509209.iam.gserviceaccount.com", ""],
        ["Ставки Ozon", "Комиссия 2,81%, Услуги 14,2%, Premium 4 990 ₽/мес", ""],
        ["Резервные копии", "backups/ — 30 последних копий ozon.db", ""],
        ["", "", ""],
        ["💡 ГЛАВНОЕ ПРАВИЛО", "", ""],
        ["", "Каждое утро: скачать .xlsx → py run.py → открыть Sheets → 3 действия → отметить «да»", ""],
        ["", "Без отметок не будет понимания, что работает. Дисциплина важнее интенсивности.", ""],
    ]
    return data


def format_manual(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    ops.append({"type": "merge", "range": "A1:C1"})
    ops.append({"type": "format", "range": "A1:C1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 44})

    section_rows = [3, 18, 26, 36, 43, 51]
    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    label_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    text_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )

    total_rows = 53
    for r in range(2, total_rows + 1):
        if r in section_rows:
            ops.append({"type": "merge", "range": f"A{r}:C{r}"})
            ops.append({"type": "format", "range": f"A{r}:C{r}", "format": section_fmt})
            ops.append({"type": "row_height", "row": r, "height": 32})
        else:
            ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
            ops.append({"type": "format", "range": f"B{r}", "format": text_fmt})
            ops.append({"type": "row_height", "row": r, "height": 26})

    ops.append({"type": "width", "col": "A", "width": 180})
    ops.append({"type": "width", "col": "B", "width": 780})
    ops.append({"type": "width", "col": "C", "width": 80})

    ops.append({"type": "frozen", "rows": 1})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")


def sync_manual(sh, con):
    print("")
    print("[Лист ИНСТРУКЦИЯ]")
    ws = get_or_create_sheet(sh, "ИНСТРУКЦИЯ")
    data = build_manual(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_manual(ws)
    # Перемещаем в начало списка вкладок
    try:
        sh.move_worksheet(ws, 0)
        print("  Перемещён на первое место")
    except Exception as e:
        print(f"  [WARN] Не удалось переместить: {e}")
'''

anchor = "def sync_today(sh, con):"
if anchor in src:
    src = src.replace(anchor, new_code + "\n\n" + anchor, 1)
    print("[OK] Функции добавлены")
else:
    print("[FAIL] Не нашёл anchor sync_today")

if "    sync_manual(sh, con)" not in src:
    old_main = "    sync_today(sh, con)"
    new_main = "    sync_manual(sh, con)\n    sync_today(sh, con)"
    if old_main in src:
        src = src.replace(old_main, new_main, 1)
        print("[OK] sync_manual добавлен в main")
    else:
        print("[FAIL] Не нашёл вызов sync_today в main")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("")
print("Готово. Запускай: py sheets_sync.py")
