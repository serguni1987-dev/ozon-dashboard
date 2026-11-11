-- Схема базы «Пульт Ozon». Файл собран командой: py -m unitka.init_db --dump

CREATE TABLE IF NOT EXISTS abc_xyz (
    period       TEXT    NOT NULL,
    sku          INTEGER NOT NULL,
    profit       REAL,
    revenue      REAL,
    qty          INTEGER,
    abc_class    TEXT,
    xyz_class    TEXT,
    matrix       TEXT,
    share_profit REAL,
    cum_share    REAL,
    cv           REAL,
    capital      REAL,
    recommendation TEXT,
    fetched_at   TEXT, active_months INTEGER, reason TEXT,
    PRIMARY KEY (period, sku)
);

CREATE TABLE IF NOT EXISTS accrual_non_item_daily (
  id             INTEGER PRIMARY KEY,
  date           TEXT NOT NULL,
  accrual_id     INTEGER,
  posting_number TEXT,
  type_id        INTEGER NOT NULL,
  amount         REAL NOT NULL,
  kind           TEXT,
  raw_json       TEXT,
  fetched_at     TEXT,
  UNIQUE(date, accrual_id, posting_number, type_id, kind)
);

CREATE TABLE IF NOT EXISTS accrual_sku_daily (
  id             INTEGER PRIMARY KEY,
  date           TEXT NOT NULL,
  accrual_id     INTEGER,
  posting_number TEXT,
  sku            INTEGER NOT NULL,
  type_id        INTEGER NOT NULL,
  amount         REAL NOT NULL,
  raw_json       TEXT,
  fetched_at     TEXT,
  UNIQUE(date, accrual_id, posting_number, sku, type_id)
);

CREATE TABLE IF NOT EXISTS accrual_types (
  id           INTEGER PRIMARY KEY,
  name         TEXT,
  description  TEXT,
  fetched_at   TEXT
);

CREATE TABLE IF NOT EXISTS accruals (
    accrual_id      INTEGER PRIMARY KEY,
    date            TEXT NOT NULL,
    sku             INTEGER,
    unit_number     TEXT,
    accrued_category TEXT,
    delivery_schema TEXT,
    seller_price    REAL,
    sale_price      REAL,
    sale_commission REAL,
    bonus           REAL,
    coinvestment    REAL,
    total_amount    REAL
, raw_json TEXT, posting_schema TEXT);

CREATE TABLE IF NOT EXISTS accruals_services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    accrual_id   INTEGER NOT NULL,
    date         TEXT NOT NULL,
    sku          INTEGER,
    type_id      INTEGER NOT NULL,
    type_name    TEXT,
    amount       REAL NOT NULL,
    FOREIGN KEY (accrual_id) REFERENCES accruals(accrual_id)
);

CREATE TABLE IF NOT EXISTS ad_campaigns_daily (
            date TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            campaign_name TEXT,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            expense REAL DEFAULT 0,
            orders INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            PRIMARY KEY (date, campaign_id)
        );

CREATE TABLE IF NOT EXISTS analytics_daily (
    date                 TEXT    NOT NULL,
    sku                  INTEGER NOT NULL,
    views_search         INTEGER,
    views_pdp            INTEGER,
    to_cart              INTEGER,
    session_view_search  INTEGER,
    ordered_units        INTEGER,
    revenue              REAL,
    conv_view_to_order   REAL,
    conv_cart_to_order   REAL,
    position_avg         REAL,
    position_category    REAL,
    raw_json             TEXT,
    fetched_at           TEXT,
    PRIMARY KEY (date, sku)
);

CREATE TABLE IF NOT EXISTS analytics_manual (
            date TEXT NOT NULL,
            sku TEXT NOT NULL,
            offer_id TEXT,
            name TEXT,
            impressions INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            cart INTEGER DEFAULT 0,
            orders INTEGER DEFAULT 0,
            buyouts INTEGER DEFAULT 0,
            position REAL,
            drr REAL,
            source_file TEXT,
            loaded_at TEXT, avg_price REAL, price_index REAL, discount_pct REAL, reviews_count INTEGER, rating REAL,
            PRIMARY KEY (date, sku)
        );

CREATE TABLE IF NOT EXISTS balance_history (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        fetched_at        TEXT NOT NULL,
        date_from         TEXT NOT NULL,
        date_to           TEXT NOT NULL,
        opening_balance   REAL,
        closing_balance   REAL,
        accrued           REAL,
        payments          REAL,
        sales_amount      REAL,
        sales_fee         REAL,
        sales_revenue     REAL,
        sales_points      REAL,
        returns_amount    REAL,
        returns_revenue   REAL,
        returns_points    REAL,
        raw_json          TEXT
    );

CREATE TABLE IF NOT EXISTS balance_periods (
    period_begin TEXT,
    period_end   TEXT,
    begin_balance REAL,
    end_balance   REAL,
    payments_total REAL,
    orders_amount REAL,
    returns_amount REAL,
    commission_amount REAL,
    services_amount REAL,
    delivery_amount REAL,
    raw_json TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (period_begin, period_end)
);

CREATE TABLE IF NOT EXISTS capital_input (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    update_date   TEXT NOT NULL,          -- YYYY-MM-DD
    on_account    REAL NOT NULL DEFAULT 0, -- ₽ на расчётном счету
    note          TEXT
);

CREATE TABLE IF NOT EXISTS change_log (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, sku TEXT, field TEXT, old_value TEXT, new_value TEXT, source TEXT, comment TEXT);

CREATE TABLE IF NOT EXISTS current_prices (
        offer_id           TEXT PRIMARY KEY,
        sku                INTEGER,
        price              REAL,
        old_price          REAL,
        min_price          REAL,
        marketing_price    REAL,
        net_price          REAL,
        currency           TEXT,
        acquiring          REAL,
        sales_percent_fbo  REAL,
        sales_percent_fbs  REAL,
        price_index_color  TEXT,
        price_index_value  REAL,
        price_index_min    REAL,
        volume_weight      REAL,
        fetched_at         TEXT
    );

CREATE TABLE IF NOT EXISTS current_stocks (
        offer_id      TEXT PRIMARY KEY,
        sku           INTEGER,
        fbo_present   INTEGER,
        fbo_reserved  INTEGER,
        fbs_present   INTEGER,
        fbs_reserved  INTEGER,
        total_present INTEGER,
        total_reserved INTEGER,
        fetched_at    TEXT
    );

CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            run_at TEXT PRIMARY KEY,
            period_from TEXT,
            period_to TEXT,
            revenue REAL,
            profit REAL,
            margin REAL,
            orders INTEGER,
            avg_check REAL
        );

CREATE TABLE IF NOT EXISTS decisions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    offer_id      TEXT NOT NULL,
    category      TEXT,
    action_text   TEXT,
    -- Снимок метрик на момент решения
    revenue_before   REAL,
    profit_before    REAL,
    margin_before    REAL,
    orders_before    INTEGER,
    views_before     INTEGER,
    carts_before     INTEGER,
    price_before     REAL,
    -- Что изменили
    price_after      REAL,
    -- Статус
    status        TEXT DEFAULT 'in_progress',
    review_at     TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS finance_payouts (
    payout_id       TEXT PRIMARY KEY,
    date            TEXT NOT NULL,
    amount          REAL,
    period_from     TEXT,
    period_to       TEXT,
    status          TEXT,
    raw_json        TEXT,
    fetched_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finance_transactions (
    operation_id    TEXT PRIMARY KEY,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL,
    operation_type  TEXT,
    amount          REAL,
    posting_number  TEXT,
    sku             TEXT,
    raw_json        TEXT,
    fetched_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS forecast (
            sku TEXT PRIMARY KEY,
            forecast_qty REAL DEFAULT 0,
            forecast_revenue REAL DEFAULT 0,
            method TEXT,
            created_at TEXT
        );

CREATE TABLE IF NOT EXISTS ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name       TEXT,
    period_from     TEXT,
    period_to       TEXT,
    rows_parsed     INTEGER,
    parsed_at       TEXT
);

CREATE TABLE IF NOT EXISTS load_log (
  id          INTEGER PRIMARY KEY,
  date        TEXT NOT NULL UNIQUE,
  status      TEXT,
  n_accruals  INTEGER DEFAULT 0,
  n_rows      INTEGER DEFAULT 0,
  error       TEXT,
  fetched_at  TEXT
);

CREATE TABLE IF NOT EXISTS monthly_realization_rows (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    month               TEXT NOT NULL,
    row_number          INTEGER,
    sku                 INTEGER,
    offer_id            TEXT,
    barcode             TEXT,
    item_name           TEXT,
    seller_price        REAL,
    sale_price          REAL,
    quantity            INTEGER,
    commission_ratio    REAL,
    gross_commission    REAL,
    bonus               REAL,
    coinvestment        REAL,
    logistics           REAL,
    total_held          REAL,
    effective_fee       REAL,
    stars               REAL,
    is_return           INTEGER DEFAULT 0,
    raw_json            TEXT
);

CREATE TABLE IF NOT EXISTS monthly_reports (
    month            TEXT PRIMARY KEY,
    year             INTEGER,
    month_num        INTEGER,
    report_number    TEXT,
    report_date      TEXT,
    period_start     TEXT,
    period_end       TEXT,
    seller_price_sum     REAL DEFAULT 0,
    sale_price_sum       REAL DEFAULT 0,
    gross_commission_sum REAL DEFAULT 0,
    bonus_sum            REAL DEFAULT 0,
    coinvestment_sum     REAL DEFAULT 0,
    logistics_sum        REAL DEFAULT 0,
    total_held_sum       REAL DEFAULT 0,
    effective_fee_sum    REAL DEFAULT 0,
    stars_sum            REAL DEFAULT 0,
    tax_base             REAL DEFAULT 0,
    tax_15               REAL DEFAULT 0,
    net_profit           REAL DEFAULT 0,
    fetched_at           TEXT,
    raw_json             TEXT
);

CREATE TABLE IF NOT EXISTS orders_created (
  posting_number TEXT,
  created_at     TEXT,
  scheme         TEXT,
  status         TEXT,
  PRIMARY KEY(posting_number, scheme)
);

CREATE TABLE IF NOT EXISTS payouts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period_begin      TEXT NOT NULL,
    period_end        TEXT NOT NULL,
    orders_amount     REAL,
    returns_amount    REAL,
    commission_amount REAL,
    services_amount   REAL,
    delivery_amount   REAL,
    total_amount      REAL,
    status            TEXT DEFAULT 'expected',
    fetched_at        TEXT
);

CREATE TABLE IF NOT EXISTS pending_orders (
        posting_number TEXT PRIMARY KEY,
        scheme         TEXT,
        status         TEXT,
        created_at     TEXT,
        in_process_at  TEXT,
        total_price    REAL,
        quantity       INTEGER,
        fetched_at     TEXT
    );

CREATE TABLE IF NOT EXISTS postings_daily (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    posting_number TEXT NOT NULL,
    sku            TEXT,
    quantity       INTEGER DEFAULT 1,
    price          REAL DEFAULT 0,
    commission     REAL DEFAULT 0,
    is_cancelled   INTEGER DEFAULT 0,
    is_returned    INTEGER DEFAULT 0,
    status         TEXT,
    source         TEXT DEFAULT 'api',
    raw_json       TEXT
);

CREATE TABLE IF NOT EXISTS price_changes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at   TEXT NOT NULL,
    offer_id     TEXT NOT NULL,
    sku          INTEGER,
    old_price    REAL,
    new_price    REAL,
    min_price    REAL,
    api_status   TEXT,      -- 'ok', 'error', 'partial'
    api_message  TEXT,
    batch_id     TEXT,      -- группировка по одному вызову API
    rolled_back  INTEGER DEFAULT 0,
    rollback_at  TEXT
);

CREATE TABLE IF NOT EXISTS procurement_plan (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    due_date      TEXT NOT NULL,          -- когда платить
    supplier      TEXT,                    -- кому
    amount        REAL NOT NULL,           -- сколько ₽
    status        TEXT DEFAULT 'planned',  -- planned / paid / cancelled
    note          TEXT
);

CREATE TABLE IF NOT EXISTS product_cost_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sku         INTEGER NOT NULL,
        date_from   TEXT NOT NULL,
        cost_price  REAL NOT NULL,
        source      TEXT DEFAULT 'manual',
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(sku, date_from)
    );

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
, is_own INTEGER DEFAULT 0, cost_price REAL, is_archived INTEGER DEFAULT 0, cost_date TEXT);

CREATE TABLE IF NOT EXISTS profit_plan (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month         TEXT NOT NULL UNIQUE,    -- YYYY-MM
    planned_profit REAL NOT NULL DEFAULT 0,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS realization_daily (
  id              INTEGER PRIMARY KEY,
  date            TEXT NOT NULL,
  accrual_id      INTEGER,
  posting_number  TEXT,
  sku             INTEGER NOT NULL,
  offer_id        TEXT,
  quantity        INTEGER DEFAULT 0,
  seller_price    REAL DEFAULT 0,
  sale_price      REAL DEFAULT 0,
  sale_amount     REAL DEFAULT 0,
  bonus           REAL DEFAULT 0,
  coinvestment    REAL DEFAULT 0,
  commission      REAL DEFAULT 0,
  commission_ratio REAL DEFAULT 0,
  delivery_total  REAL DEFAULT 0,
  is_return       INTEGER DEFAULT 0,
  raw_json        TEXT,
  fetched_at      TEXT,
  UNIQUE(date, accrual_id, posting_number, sku)
);

CREATE TABLE IF NOT EXISTS returns_daily (
            return_id TEXT PRIMARY KEY,
            date TEXT,
            sku TEXT,
            offer_id TEXT,
            posting_number TEXT,
            quantity INTEGER,
            price REAL,
            reason TEXT,
            schema TEXT,
            status TEXT,
            raw_json TEXT,
            fetched_at TEXT
        );

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

CREATE TABLE IF NOT EXISTS seasonality (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            total_quantity INTEGER DEFAULT 0,
            total_revenue REAL DEFAULT 0,
            season_index REAL DEFAULT 0,
            PRIMARY KEY (year, month)
        );

CREATE TABLE IF NOT EXISTS sku_content_rating (
            sku TEXT PRIMARY KEY,
            content_rating REAL,
            updated_at TEXT
        );

CREATE TABLE IF NOT EXISTS sku_map (
            ozon_sku        TEXT PRIMARY KEY,
            offer_id        TEXT,
            stock_sku       TEXT,
            source          TEXT,
            match_confidence TEXT,
            updated_at      TEXT
        );

CREATE TABLE IF NOT EXISTS sku_ratings (
            sku TEXT PRIMARY KEY,
            rating REAL,
            reviews_count INTEGER,
            updated_at TEXT
        );

CREATE TABLE IF NOT EXISTS sku_reviews (sku TEXT PRIMARY KEY, avg_rating REAL, total_reviews INTEGER, bad_reviews INTEGER, fetched_at TEXT);

CREATE TABLE IF NOT EXISTS stock_daily (
            date TEXT NOT NULL,
            sku TEXT NOT NULL,
            fbo_present INTEGER DEFAULT 0,
            fbo_reserved INTEGER DEFAULT 0,
            fbs_present INTEGER DEFAULT 0,
            fbs_reserved INTEGER DEFAULT 0,
            PRIMARY KEY (date, sku)
        );

CREATE TABLE IF NOT EXISTS transactions (
    operation_id    TEXT PRIMARY KEY,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL,
    operation_type  TEXT,
    amount          REAL,
    posting_number  TEXT,
    sku             TEXT,
    raw_json        TEXT,
    fetched_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_abc_xyz_matrix ON abc_xyz(period, matrix);

CREATE INDEX IF NOT EXISTS idx_abc_xyz_period ON abc_xyz(period);

CREATE INDEX IF NOT EXISTS idx_accruals_date ON accruals(date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_accruals_services_unique
    ON accruals_services(
        accrual_id, type_id, date, amount,
        COALESCE(sku, -1)
    );

CREATE INDEX IF NOT EXISTS idx_accruals_sku  ON accruals(sku);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_date ON analytics_daily(date);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_sku  ON analytics_daily(sku, date);

CREATE INDEX IF NOT EXISTS idx_anid_date ON accrual_non_item_daily(date);

CREATE INDEX IF NOT EXISTS idx_asd_date     ON accrual_sku_daily(date);

CREATE INDEX IF NOT EXISTS idx_asd_date_sku ON accrual_sku_daily(date, sku);

CREATE INDEX IF NOT EXISTS idx_bh_fetched ON balance_history(fetched_at);

CREATE INDEX IF NOT EXISTS idx_ci_date ON capital_input(update_date);

CREATE INDEX IF NOT EXISTS idx_cost_history_sku_date
    ON product_cost_history(sku, date_from);

CREATE INDEX IF NOT EXISTS idx_cp_color ON current_prices(price_index_color);

CREATE INDEX IF NOT EXISTS idx_cp_sku ON current_prices(sku);

CREATE INDEX IF NOT EXISTS idx_cs_sku ON current_stocks(sku);

CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);

CREATE INDEX IF NOT EXISTS idx_decisions_offer ON decisions(offer_id);

CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

CREATE INDEX IF NOT EXISTS idx_finance_payouts_date ON finance_payouts(date);

CREATE INDEX IF NOT EXISTS idx_finance_transactions_date ON finance_transactions(date);

CREATE INDEX IF NOT EXISTS idx_finance_transactions_type ON finance_transactions(type);

CREATE INDEX IF NOT EXISTS idx_mrr_month ON monthly_realization_rows(month);

CREATE INDEX IF NOT EXISTS idx_mrr_sku ON monthly_realization_rows(sku);

CREATE INDEX IF NOT EXISTS idx_pc_changed ON price_changes(changed_at);

CREATE INDEX IF NOT EXISTS idx_pc_offer ON price_changes(offer_id);

CREATE INDEX IF NOT EXISTS idx_pc_rolled ON price_changes(rolled_back);

CREATE INDEX IF NOT EXISTS idx_pending_scheme ON pending_orders(scheme);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_orders(status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_po_period ON payouts(period_begin, period_end);

CREATE INDEX IF NOT EXISTS idx_postings_date    ON postings_daily(date);

CREATE INDEX IF NOT EXISTS idx_postings_posting ON postings_daily(posting_number);

CREATE INDEX IF NOT EXISTS idx_pp_due ON procurement_plan(due_date);

CREATE INDEX IF NOT EXISTS idx_rd_date     ON realization_daily(date);

CREATE INDEX IF NOT EXISTS idx_rd_date_sku ON realization_daily(date, sku);

CREATE INDEX IF NOT EXISTS idx_rd_sku      ON realization_daily(sku);

CREATE INDEX IF NOT EXISTS idx_sales_date   ON sales_daily(date);

CREATE INDEX IF NOT EXISTS idx_sales_sku    ON sales_daily(sku);

CREATE INDEX IF NOT EXISTS idx_services_date ON accruals_services(date);

CREATE INDEX IF NOT EXISTS idx_services_type ON accruals_services(type_id);

CREATE INDEX IF NOT EXISTS idx_sku_map_offer ON sku_map(offer_id);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);

CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);

CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders_created(created_at);
