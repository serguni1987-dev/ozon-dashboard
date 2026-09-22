-- ============================================================
-- Ozon Analytics DB Schema v1
-- Файл: ozon.db (SQLite)
-- ============================================================

-- Справочник товаров (одна строка на SKU, обновляется при парсинге)
CREATE TABLE IF NOT EXISTS products (
    sku             INTEGER PRIMARY KEY,
    offer_id        TEXT,           -- артикул
    name            TEXT,
    category_l1     TEXT,
    category_l2     TEXT,
    category_l3     TEXT,
    brand           TEXT,
    model           TEXT,
    scheme          TEXT,           -- FBS, FBO
    first_seen      TEXT,           -- YYYY-MM-DD, первое появление в отчётах
    last_seen       TEXT            -- YYYY-MM-DD, последнее появление
);

-- Метрики по дням (главная таблица)
CREATE TABLE IF NOT EXISTS sales_daily (
    sku             INTEGER NOT NULL,
    date            TEXT NOT NULL,  -- YYYY-MM-DD

    -- ABC-анализ (буква A/B/C или NULL)
    abc_revenue     TEXT,
    abc_orders      TEXT,

    -- Финансы
    revenue                    REAL,   -- заказано на сумму (по цене реализации)
    revenue_max_price          REAL,   -- заказано на сумму (по предельной цене)
    revenue_share              REAL,   -- доля в общей сумме (0..1)
    avg_price                  REAL,
    discount_pct               REAL,   -- скидка от медианной (0..1)
    drr                        REAL,   -- ДРР (0..1)

    -- Позиция и индекс цен
    position_search            INTEGER,
    price_index                TEXT,   -- Без индекса / Супер-выгодный / Выгодный / Умеренный / Невыгодный

    -- Трафик — всего
    views_total                INTEGER,
    visitors_total             INTEGER,

    -- Трафик — поиск
    views_search               INTEGER,
    visitors_search            INTEGER,
    conv_view_to_order         REAL,   -- конверсия из показа в заказ (0..1)

    -- Трафик — карточка (PDP)
    pdp_visits                 INTEGER,   -- посещения карточки товара
    pdp_visitors               INTEGER,   -- уникальные посетители карточки
    conv_search_to_pdp         REAL,      -- конверсия из поиска в карточку (0..1)

    -- Корзина — поиск
    cart_adds_search           INTEGER,
    conv_search_to_cart        REAL,

    -- Корзина — карточка
    cart_adds_pdp              INTEGER,
    conv_pdp_to_cart           REAL,

    -- Корзина — всего
    cart_adds_total            INTEGER,
    conv_to_cart_total         REAL,   -- конверсия в корзину общая

    -- Заказы
    orders_units               INTEGER,   -- заказано товаров
    conv_cart_to_order         REAL,      -- конверсия из корзины в заказ
    delivered                  INTEGER,   -- доставлено товаров
    purchased                  INTEGER,   -- выкуплено товаров
    conv_order_to_purchase     REAL,      -- конверсия из заказа в выкуп
    cancelled                  INTEGER,   -- отменено (на дату заказа)
    returned_by_return_date    INTEGER,   -- возвращено (на дату возврата)
    returned_by_order_date     INTEGER,   -- возвращено (на дату заказа)

    -- Продвижение
    days_in_promo              INTEGER,   -- дней в акциях (числитель)
    days_in_promo_total        INTEGER,   -- дней в акциях (знаменатель, из "1 из 1")
    days_with_ads              INTEGER,   -- дней с продвижением (числитель)
    days_with_ads_total        INTEGER,   -- дней с продвижением (знаменатель)

    -- Склад и репутация
    stock                      INTEGER,   -- остаток на конец периода (NULL если "–")
    reviews                    INTEGER,
    rating                     REAL,

    PRIMARY KEY (sku, date)
);

CREATE INDEX IF NOT EXISTS idx_sales_date   ON sales_daily(date);
CREATE INDEX IF NOT EXISTS idx_sales_sku    ON sales_daily(sku);

-- Метаданные парсинга (когда какой файл загружали)
CREATE TABLE IF NOT EXISTS ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name       TEXT,
    period_from     TEXT,
    period_to       TEXT,
    rows_parsed     INTEGER,
    parsed_at       TEXT
);