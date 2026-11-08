unitka — пакет управленческого учёта Ozon
Единый пакет для магазина VIVA HOME TEXTILE (FBS + FBO). Содержит два независимых пайплайна:

Юнит-экономика — детализация по каждому SKU (маржа, ROI, налог).

Финансовый блок — управленка по магазину в целом (дебиторка, баланс, налоги, ДДС, оборотный капитал, деньги в товаре).

Оба пайплайна пишут в одну БД (app/ozon.db), но в разные листы Google Sheets. Работают независимо друг от друга.

Быстрый старт
powershell
cd C:\Users\sergu\Desktop\проект

# Юнит-экономика (лист «Юнит экономика»)
python -m unitka.run_unit

# Финансовый блок (все 6 финансовых листов одной командой)
python -m unitka.run_finance

# Только пересчитать листы (без запросов к API Ozon)
python -m unitka.run_finance --skip-fetch
Структура пакета
text
unitka\
│
│ ─── ОБЩИЕ МОДУЛИ ─────────────────────────────────────────────
├── config.py                   # ключи, пути, константы
├── db.py                       # схема и подключение к ozon.db
├── ozon_client.py              # HTTP-клиент Ozon API с retry
│
│ ─── ЮНИТ-ЭКОНОМИКА ───────────────────────────────────────────
├── load_accrual_types.py       # справочник типов начислений
├── load_costs.py               # себестоимость: costs_all.csv -> БД
├── load_realization_daily.py   # начисления: /v1/finance/accrual/by-day
├── load_postings.py            # FBS: /v3/posting/fbs/list
├── load_postings_fbo.py        # FBO: /v2/posting/fbo/list
├── load_postings_report.py     # резерв: XLSX SELLER_POSTINGS
├── calc_margin.py              # расчёт + запись в лист «Юнит экономика»
├── run_unit.py                 # оркестратор юнит-экономики
│
│ ─── ФИНАНСОВЫЙ БЛОК ──────────────────────────────────────────
├── load_transactions.py        # транзакции и выплаты
├── load_stocks.py              # остатки складов: /v4/product/info/stocks
├── calc_receivables.py         # лист «Дебиторка / Выплаты»
├── calc_balance.py             # лист «Баланс»
├── calc_taxes.py               # лист «Налоги» (УСН 15%)
├── calc_cashflow.py            # лист «ДДС»
├── calc_working_capital.py     # лист «Оборотный капитал» (CCC + ROI)
├── calc_money_in_goods.py      # лист «Деньги в товаре» (неликвид, дни запаса)
├── run_finance.py              # оркестратор финансов (8 шагов)
│
│ ─── ДИАГНОСТИКА ───────────────────────────────────────────────
├── _diag\                      # диагностические скрипты
├── _patches\                   # история правок
└── _dumps\                     # JSON-дампы отладки
Пайплайны
1. Юнит-экономика (run_unit.py)
5 шагов подряд. Если любой падает — остальные не идут (жёсткая цепочка).

#	Модуль	Источник данных
1	load_costs	costs_all.csv
2	load_realization_daily	/v1/finance/accrual/by-day
3	load_postings	/v3/posting/fbs/list
4	load_postings_fbo	/v2/posting/fbo/list
5	calc_margin	БД + Google Sheets
2. Финансовый блок (run_finance.py)
8 шагов. Каждый шаг изолирован — если один падает, остальные продолжают работу.

#	Модуль	Источник данных	Лист Google Sheets
1	load_transactions	/v1/finance/accrual/by-day + cash-flow-statement	—
2	load_stocks	/v4/product/info/stocks	—
3	calc_receivables	finance_transactions + finance_payouts	«Дебиторка / Выплаты»
4	calc_balance	stock_daily + product_cost_history + ручной ввод	«Баланс»
5	calc_taxes	accruals + finance_transactions + product_cost_history	«Налоги»
6	calc_cashflow	finance_payouts + ручной ввод	«ДДС»
7	calc_working_capital	все таблицы	«Оборотный капитал»
8	calc_money_in_goods	stock_daily + realization_daily	«Деньги в товаре»
Флаги run_finance.py:

--from YYYY-MM-DD --to YYYY-MM-DD — конкретный период

--days N — N дней назад (по умолчанию 7)

--skip-fetch — только пересчитать листы, без запросов к API

Google Sheets
ID: 1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0

Креды: app\credentials.json

Лист настроек: «НАСТРОЙКИ»

Листы от юнит-экономики
«Юнит экономика»: 48 колонок. По каждому SKU показывает: продажи, выкупы, отмены, выручку, комиссии, логистику, себестоимость, маржу, налог, прибыль, ROI.

«НАСТРОЙКИ»: B1 — ставка налога, B2/B3 — период.

Листы от финансового блока
«Дебиторка / Выплаты»: Сколько Ozon должен на текущую дату. Сводка + детализация транзакций и выплат.

«Баланс»: Активы (товар, дебиторка, деньги) и Пассивы (налоги, кредиторка). Собственный капитал = Активы − Пассивы.

«Налоги»: Расчёт УСН 15% + страховых взносов ИП + календарь платежей.

«ДДС»: Движение денег по месяцам (выплаты Ozon vs ручные расходы).

«Оборотный капитал»: CCC (Финансовый цикл) и ROI (Прибыль / Капитал).

«Деньги в товаре»: Замороженный капитал. Остатки × себестоимость. Дни запаса и статус (Ходовой / Избыток / Неликвид).

Служебные листы (для менеджера)
«📖 ИНСТРУКЦИЯ»: Пошаговая инструкция по работе с таблицей.

«Ручной ввод»: A1 — Деньги на счете, A2 — Кредиторка, A3 — Уплачено налогов.

«ДДС Ввод»: Расходы по месяцам (закупки, налоги, личные траты).

Автоматизация в Google Sheets (Apps Script)
Меню «💰 Финблок»: Инструкция по обновлению и ручной вызов чек-листа.

Всплывающее окно: При открытии таблицы показывает, какие ячейки не заполнены (1 раз в день).

Условное форматирование: Пустые ячейки в «Ручном вводе» и «ДДС Вводе» подсвечиваются.

Ручной ввод (Важно!)
Система не может узнать ваши банковские выписки или долги поставщикам по API Ozon. Поэтому для точности используются два листа:

«Ручной ввод» (влияет на Баланс, Налоги, ДДС).

«ДДС Ввод» (влияет на остаток денег в ДДС).

База данных (новые таблицы)
Все таблицы — в app/ozon.db.

finance_transactions — начисления и удержания (operation_id PK, date, type, amount).

finance_payouts — выплаты (payout_id PK, date, amount).

stock_daily — снимок остатков (date, sku, fbo_present, fbs_present).

realization_daily, accrual_sku_daily, accrual_non_item_daily, accrual_types, postings_daily, product_cost_history, load_log — из старого пайплайна (юнитка).

Логика расчётов
Прибыль (используется в ROI и Налогах)
profit = sale_price + bonus + coinvestment − cogs − ozon_expenses

Налог УСН 15%
tax_base = (sale_price + bonus + coinvestment) − cogs − ozon_expenses
tax_15 = max(0, tax_base × 0.15)
min_tax = sale_price × 0.01
tax_to_pay = max(tax_15, min_tax) − уплачено
Если бизнес в убытке — платим минимальный 1% с дохода.

Деньги в товаре
Сумма = Остаток (FBO+FBS) × Себестоимость
Дни запаса = Остаток / (Продажи за 30 дней / 30)
Статус: 🟢 Ходовой (<30 дней), 🟡 Избыток (30-60), 🔴 Неликвид (>60 или нет продаж).

Автоматизация (Windows)
Задача в Планировщике Windows: Ozon PNL Daily Update

Запуск: ежедневно в 09:00

Скрипт: app/daily_update.ps1

Что делает:

Старый пайплайн P&L (app/)
Юнит-экономика: python -m unitka.run_unit
Финансы: python -m unitka.run_finance --days 7
Кнопка на рабочем столе: Файл Обновить финблок.bat (двойной клик запускает run_finance --skip-fetch).

Известные ограничения
История
/v3/posting/fbs/list — данные за ~3 месяца.
/v1/finance/accrual/by-day — данные за ~1 год.

Себестоимость
Если у SKU нет cost_price — cogs = 0, маржа и прибыль завышены. Товар на складе в Балансе = 0.

VPN
Ozon API и Google API блокируются из РФ. Без VPN — таймаут. Проверка: nslookup api-seller.ozon.ru.

Налог в P&L vs лист «Налоги»
В старом листе P&L налог считается по упрощённой формуле (~7% от выручки). В новом листе «Налоги» — по правилам УСН 15%. Ориентируйтесь на «Налоги».

Диагностика и Частые проблемы
mergeCells: You must select all cells...
Безвредно. Скрипт ловит и продолжает. На цифры не влияет.

Товар на складе = 0
Запустите python -m unitka.load_stocks. Проверьте себестоимость.

ДДС показывает завышенный остаток
Не вписаны расходы в лист «ДДС Ввод».

ModuleNotFoundError: No module named 'unitka.xxx'
Запуск должен быть из корня проекта (C:\Users\sergu\Desktop\проект).

Связанные документы
README.md — краткая инструкция по всему проекту (общая карта).

README_FINANCE.md — этот документ (полная документация пакета unitka).

Файлы в корне проекта
Файл / папка	Назначение
unitka\	этот пакет (юнитка + финблоки)
app\	старый пайплайн P&L + база данных
app\ozon.db	единая база данных SQLite
app\.env	ключи Ozon API
app\credentials.json	сервисный аккаунт Google
costs_all.csv	себестоимость (правится вручную)
README.md	общая карта проекта
README_FINANCE.md	документация пакета unitka (этот файл)