# PNL — лист P&L в Google Sheets

Папка скриптов для генерации и оформления листа **P&L** в проекте «Пульт Ozon».
Этот README — точка входа для быстрого понимания структуры.

---

## Контекст проекта

- **Магазин:** VIVA HOME TEXTILE (ИП Метельков С.В.)
- **Платформа:** Ozon Seller
- **Google Sheets ID:** `1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0`
- **Лист:** `P&L` (50 строк × 19 колонок)
- **БД:** `../ozon.db` (SQLite, 12 МБ)
- **Credentials:** `../credentials.json` (сервисный аккаунт Google)
- **Env:** `../.env` (OZON_CLIENT_ID, OZON_API_KEY)

---

## Ядро (3 файла)

| Файл | Что делает | Когда запускать |
|---|---|---|
| **sync_pnl.py** | Собирает P&L из БД, пишет в Google Sheets. Поддерживает `--local` (только CSV, без записи в Sheets). | После обновления БД (`sync_monthly`, `sync_finance`) |
| **pnl_format.py** | Накладывает стиль: цвета блоков, границы, ширины, freeze, примечания. Значения НЕ трогает. | После каждого `sync_pnl.py` |
| **fix_sheet_full.py** | Записывает «живые» формулы (B, O:R) с `value_input_option=USER_ENTERED`, чтобы Google их считал. | После `pnl_format.py` |

### Порядок запуска после обновления данных
py PNL\sync_pnl.py 2026
py PNL\pnl_format.py
py PNL\fix_sheet_full.py


Без `fix_sheet_full` формулы в колонке B и кварталах останутся текстом.

---

## Структура листа P&L (50 строк)

| № | Строка | Тип |
|---|---|---|
| 1 | Отчёт о прибылях и убытках OZON | заголовок |
| 2 | Всего за 2026 / янв..дек / 1..4 кв | шапка |
| 3–6 | СПРАВОЧНО: заказы, баллы, всего к начислению, сумма отчёта | серые |
| **8** | **ДОХОДЫ** | зелёный |
| 9–12 | Выручка, Баллы за скидки, Программы партнёров, Компенсации | обычные |
| **14** | **Прямые (переменные) расходы** | оранжевый |
| 15 | Озон комиссия | обычная |
| **16** | **Озон фулфилмент** | bold |
| 17–20 | – логистика / обратная / последняя миля / обработка | серые italic |
| **21** | **Озон маркетинг** | bold |
| 22–26 | – реклама (PPC) / промо / звёзды / бренд / отзывы | серые italic |
| 27–30 | Услуги агентов, FBO, Другие, Прочие | обычные |
| 32 | Себестоимость | красный |
| **34** | **ВАЛОВАЯ ПРИБЫЛЬ** | зелёный |
| **36** | **Операционные расходы (всего)** | авто-SUM(37:40) |
| 37–40 | Персонал / Админ / Коммерч / Прочие | **ручной ввод в C:N** |
| **42** | **EBITDA** = 34 − 36 | зелёный |
| 44 | Налоги (УСН 15%) | красный |
| **46** | **ЧИСТАЯ ПРИБЫЛЬ** = 42 + 44 | зелёный/красный |
| 47 | ROI = −46/32×100 | серый italic |
| 49–50 | Нераспределённая / Накопленная | зелёный |

---

## Ключевые формулы

- **Год (B):** `=SUM(C..N)`
- **Кварталы (O:R):** `=SUM(месяц1:месяц3)`
- **36 Операционные:** `=SUM(37:40)` по каждой колонке
- **42 EBITDA:** `=B34-B36`
- **46 Чистая:** `=B42+B44` (в 44 налог уже со знаком минус)
- **47 ROI:** `=IF(B32=0;0;-B46/B32*100)`

---

## Классификация услуг Ozon (CATEGORY_MAP в sync_pnl.py)

Маппинг `type_id` → категория P&L. Построен по `type_name` из Ozon API (таблица `accruals_services`).

**Фулфилмент:**
- Логистика: 32 (Logistic), 77 (SupplyInbound)
- Обратная: 59 (ReturnFlowLogistic), 71 (SellerReturns), 45 (PickUpPointReturnAcceptance)
- Последняя миля: 29 (LastMileCourier), 98 (DeliveryToHandoverPlaceByOzon)
- Обработка: 12, 16, 38, 39, 78, 79

**Маркетинг:**
- PPC: 41 (PayPerClick)
- Промо: 54 (Promotion)
- Звёзды: 74 (StarsMembership)
- Бренд: 3 (BrandCommission)
- Отзывы: 47 (PointsForReviews), 96 (AcceleratedReviewCollection)

**Агенты:** 1, 18, 20, 22
**FBO:** 46, 76
**Другие:** 14, 15, 48, 52, 93, 94
**Прочие:** 6, 9, 40

---

## Диагностика (11 файлов)

| Файл | Что показывает |
|---|---|
| `diag_july.py` | Наполнение БД за июнь/июль |
| `diag_names.py` | type_id + type_name + суммы за 2026 |
| `diag_service_types.py` | Все type_id в accruals_services |
| `diag_formulas.py` | Формулы и значения ключевых ячеек листа |
| `diag_pnl.py` | Общая диагностика листа P&L |
| `check_csv_aug.py` | Сверка CSV августа: J16=J17+..+J20, J21=J22+J23 |
| `read_pnl_csv.py` | Печать pnl_2026.csv |
| `check_pnl_cols.py` | Проверка колонок листа |
| `peek_august.py` | Read-only запрос к Ozon API за август |
| `peek_agg.py` | Агрегаты по peek_august_raw.json |
| `test_returns.py` | Проверка вычета возвратов в отчёте реализации |

---

## Архив патчей (`_archive/`, 35 файлов)

Одноразовые скрипты `patch_*.py`, `fix_*.py`, `add_*.py`, которые уже применены и привели код к текущему виду. Запускать не нужно — оставлены для истории.

---

## Частые проблемы

**1. Формулы в колонке B показываются как текст**
Значит `sync_pnl.py` записал их в RAW. Лечится: `py PNL\fix_sheet_full.py`.

**2. Стиль слетел после sync**
`sync_pnl.py` пишет через `ws.update`, который стирает фон. Лечится: `py PNL\pnl_format.py`.

**3. Август показывает 178 504,96 вместо 161 382,96**
БД хранит устаревшую версию отчёта. Лечится: `py sync_monthly.py` (вычитает возвраты).

**4. Ошибка "getaddrinfo failed"**
VPN не работает. Google API недоступен из РФ без VPN. Проверка: `nslookup oauth2.googleapis.com`.

**5. Июнь-июль пустые в строках 16–30**
В `accruals_services` нет данных за эти месяцы. Нужен `sync_finance.py` с диапазоном дат.

---

## Пути

- Рабочий ПК: `C:\Users\PTO\Проект\ozon-dashboard\app\PNL\`
- Ноутбук: `C:\Users\sergu\Desktop\проект\app\PNL\`
- GitHub: https://github.com/serguni1987-dev/ozon-dashboard

---

## Структура папки PNL

- **Ядро** (3): `sync_pnl.py`, `pnl_format.py`, `fix_sheet_full.py`
- **`_diag/`** — диагностика P&L (36 файлов)
- **`_archive/`** — одноразовые патчи (51 файл), уже применены

### Запуск диагностики

Из папки `app/`:

    py PNL\_diag\check_all_cogs.py
    py PNL\_diag\compare_ozon.py

### Что НЕ переносить из app/

- `mark_brands.py`, `check_costs_alert.py` — вызываются из `run.py`
- `run_pnl.bat` — вызывается из корня `app\`
- `import_costs.py`, `export_all_costs.py` — про себестоимость, влияет на ЦЕНЫ
- `sync_finance.py`, `sync_monthly.py`, `sheets_sync.py`, `run.py` — общие
- `sync_fact.py`, `calc_fact_exact.py`, `read_fact.py` — лист ФАКТ

---

## Себестоимость

### Файл
`проект/costs_all.csv` — редактируй тут (Excel, разделитель `;`, UTF-8).

### Формат
offer_id;sku;name;category_l2;cost_price;date_from;comment
- `cost_price` — пусто, если цены нет (SKU не влияет на P&L)
- `date_from` — `YYYY-MM-DD`, дата начала действия. Пусто → сегодня.

### История цен
Таблица `product_cost_history(sku, date_from, cost_price, source, created_at)`.

P&L берёт цену на конец месяца через `date_from < конец_месяца`.

### Workflow
1. `py export_all_costs.py` — выгрузить все SKU в `проект/costs_all.csv`
2. Заполнить `cost_price` в Excel
3. `py import_costs.py` — залить в БД + историю

### Скрипты
- `import_costs.py` — Excel → БД (products + history)
- `export_all_costs.py` — БД → Excel
- `create_cost_history.py` — однократно создал таблицу
- `migrate_costs_csv.py` — однократно перенёс старый CSV


