\# Себестоимость — управление ценами закупки



Папка скриптов для работы с себестоимостью товаров (закупочная цена).



\## Что тут



\### Ядро (4 файла)



| Файл | Что делает |

|---|---|

| `import\_costs.py` | Читает `проект/costs\_all.csv`. \*\*Применяет только колонки 7–8\*\* (`cost\_price\_new`, `date\_from\_new`). Обновляет `products` + пишет в `product\_cost\_history` |

| `export\_all\_costs.py` | Выгружает все свои SKU в `проект/costs\_all.csv` (8 колонок) + справочный `costs\_all\_info.csv` |

| `create\_cost\_history.py` | Однократно создал таблицу `product\_cost\_history` и заполнил текущими ценами |

| `migrate\_costs\_csv.py` | Однократно перенёс старый CSV в новый формат с `date\_from` |



\### Диагностика (`\_diag/`, 11 файлов)



Проверки покрытия, пустых цен, дублей — запускать по необходимости.



\### Архив (`\_archive/`, 7 файлов)



Одноразовые скрипты (миграции, старые импорты) — \*\*не запускать\*\*.



\## Файл данных



`проект/costs\_all.csv` — редактируй в Excel.



\### Формат

offer\_id;sku;name;category\_l2;cost\_price;date\_from;cost\_price\_new;date\_from\_new





| Колонка | Что |

|---|---|

| `offer\_id`, `sku`, `name`, `category\_l2` | Справочно, не трогать |

| `cost\_price`, `date\_from` | \*\*Текущая цена\*\* (справочно, скрипт не трогает) |

| \*\*`cost\_price\_new`, `date\_from\_new`\*\* | \*\*Заполни, если меняешь цену.\*\* `date\_from\_new` — `YYYY-MM-DD` (с какого числа) |



\### Workflow изменения цены



1\. `py Себестоимость\\export\_all\_costs.py` — выгрузить CSV

2\. Открыть `проект/costs\_all.csv` в Excel

3\. Найти нужный SKU

4\. Заполнить `cost\_price\_new` (новая цена) и `date\_from\_new` (дата начала)

5\. Сохранить (Ctrl+S)

6\. `py Себестоимость\\import\_costs.py` — применить



Скрипт:

\- добавит запись в `product\_cost\_history`

\- обновит `products.cost\_price`



P\&L (`PNL/sync\_pnl.py`) возьмёт \*\*правильную цену на конец каждого месяца\*\* из истории.



\## Таблица `product\_cost\_history`

sku | date\_from | cost\_price | source | created\_at





\- `source = 'migration'` — заполнено при создании таблицы (01.01.2026)

\- `source = 'import'` — добавлено через `import\_costs.py`



\## Пути



\- Скрипты: `app/Себестоимость/`

\- Данные: `проект/costs\_all.csv`

\- БД: `app/ozon.db`



\## Что НЕ переносить сюда



\- `check\_cost
s\_alert.py` — вызывается из `run.py` (корень `app/`)

\- `mark\_brands.py` — влияет на ЦЕНЫ/ОСТАТКИ, не только на себестоимость

\- `check\_cogs\_logic.py` — про P\&L, лежит в `PNL/\_diag/`

