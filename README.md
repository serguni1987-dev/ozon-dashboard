# Ozon Dashboard

Дашборд для управления магазином на Ozon: продажи, маржа, реклама, деньги, решения.

## Структура

- `app/` — весь код проекта
  - `run.py` — главная точка входа
  - `sheets_sync.py` — синхронизация с Google Sheets
  - `plan_core.py` — генерация плана действий
  - `01_product_cards/`…`08_reporting/` — модули по категориям
  - `downloads/` — выгрузки из Ozon (не в Git)
  - `backups/` — бэкапы БД (не в Git)

## Что НЕ в Git

- `.env` — ключи Ozon
- `credentials.json` — ключи Google
- `ozon.db` — база данных
- `config.json` — настройки
- `downloads/`, `backups/` — данные

Всё это переносится между ПК через флешку/Яндекс.Диск.

## Установка
