src = open("sync_pnl.py", encoding="utf-8").read()

old = '''    # Разделы
    section_rows = [6, 12, 28, 30, 36, 38, 40]
    for r in section_rows:
        fmt(f"A{r}:S{r}", bg=GREEN, bold=True)

    # Все значения — вправо
    for r in range(2, n_rows + 1):
        if r in section_rows:
            continue
        fmt(f"B{r}:S{r}", align="RIGHT", size=10)
        fmt(f"A{r}", size=10)'''

new = '''    # Разделы (реальные номера строк)
    GREEN_SECTIONS = [8, 30, 38, 42]      # доходы, валовая, EBITDA, чистая
    RED_SECTIONS = [14]                    # прямые расходы
    GREY_SECTIONS = [32, 40]              # операционные, налоги

    for r in GREEN_SECTIONS:
        fmt(f"A{r}:S{r}", bg=GREEN, bold=True)
    for r in RED_SECTIONS:
        fmt(f"A{r}:S{r}", bg=RED, bold=True)
    for r in GREY_SECTIONS:
        fmt(f"A{r}:S{r}", bg=GREY, bold=True)

    # Все остальные значения — вправо
    skip = set(GREEN_SECTIONS + RED_SECTIONS + GREY_SECTIONS)
    for r in range(2, n_rows + 1):
        if r in skip:
            continue
        fmt(f"B{r}:S{r}", align="RIGHT", size=10)
        fmt(f"A{r}", size=10)

    # Формулы года и кварталов — тоже выравнивание
    for r in range(2, n_rows + 1):
        fmt(f"B{r}", bg=GREY, align="RIGHT", size=10, bold=False)
        fmt(f"O{r}:R{r}", bg=GREY, align="RIGHT", size=10, bold=False)'''

if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] Форматирование исправлено — реальные номера строк")
else:
    print("[?] Не нашёл блок форматирования")
