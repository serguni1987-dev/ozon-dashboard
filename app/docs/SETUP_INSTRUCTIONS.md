# Инструкция по запуску проекта

## Шаг 1: GitHub репозиторий

1. Создайте репозиторий на GitHub: `ozon-marketplace-management`
2. Клонируйте на локальную машину:
   ```bash
   git clone https://github.com/yourusername/ozon-marketplace-management.git
   ```
3. Скопируйте файлы проекта в репозиторий
4. Закоммитьте и отправьте:
   ```bash
   git add .
   git commit -m "Initial project structure"
   git push origin main
   ```

## Шаг 2: Настройка конфигурации

1. Скопируйте `config_template.json` в `config.json`:
   ```bash
   cp config_template.json config.json
   ```

2. Вставьте свои данные:
   ```json
   {
       "ozon_api": {
           "client_id": "YOUR_CLIENT_ID",
           "api_key": "YOUR_API_KEY",
           "base_url": "https://api-seller.ozon.ru"
       },
       "google_api": {
           "credentials_file": "credentials.json",
           "spreadsheet_id": "YOUR_SPREADSHEET_ID"
       }
   }
   ```

3. **Важно:** Не коммитьте `config.json` в git (он в `.gitignore`)

## Шаг 3: Установка зависимостей

```bash
pip install requests pandas openpyxl gspread oauth2client
```

## Шаг 4: Google Таблицы

1. Создайте новую Google Таблицу: `Ozon Marketplace Management`
2. Создайте 8 листов (см. `templates/google_sheets_structure.md`)
3. Получите `spreadsheet_id` из URL таблицы
4. Настройте Google API:
   - Создайте проект в Google Cloud Console
   - Включите Google Sheets API
   - Создайте сервисный аккаунт
   - Скачайте `credentials.json`
   - Дайте доступ сервисному аккаунту к таблице

## Шаг 5: Тестовая выгрузка

1. Запустите скрипт выгрузки:
   ```bash
   cd scripts
   python ozon_api_export.py
   ```

2. Проверьте файлы в `assets/exports/`:
   - `products.csv`
   - `product_details.csv`
   - `pricing.csv`
   - `analytics.csv`
   - `reviews.csv`
   - `sales.csv`
   - `advertising.csv`
   - `finance.csv`
   - `stocks.csv`

## Шаг 6: Импорт в Google Таблицы

1. Откройте вашу таблицу
2. Файл → Импорт → Загрузить
3. Загрузите каждый CSV в соответствующий лист

## Шаг 7: Notion база знаний

1. Создайте workspace в Notion
2. Создайте базу знаний: `Ozon Marketplace Management`
3. Создайте страницы:
   - Процессы и регламенты
   - Шаблоны
   - Отчёты
   - История изменений
4. Скопируйте содержимое из `docs/` и `templates/`

## Шаг 8: Автоматизация (опционально)

### Ежедневная выгрузка
Настройте cron job (Linux/Mac) или Task Scheduler (Windows):

```bash
# Ежедневно в 09:00
0 9 * * * cd /path/to/project && python scripts/daily_export.py
```

### Уведомления
Настройте уведомления в Telegram/Slack при:
- Падении продаж >20%
- Низкий рейтинг <4.0
- Out-of-stock
- Превышение бюджета

## Шаг 9: Запуск пилота

1. Выберите 10–20 SKU для пилота
2. Проведите полный аудит карточек
3. Внесите приоритетные правки
4. Присвойте статус «готова к рекламе"
5. Запустите тестовые рекламные кампании

## Шаг 10: Масштабирование

1. Аудит всего ассортимента
2. Создание шаблонов для групп SKU
3. Массовое обновление карточек
4. Отбор локомотивов
5. Запуск полноценной рекламы

## Поддержка

- Вопросы: создайте Issue на GitHub
- Документация: см. `docs/`
- Шаблоны: см. `templates/`