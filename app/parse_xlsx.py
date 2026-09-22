"""
parse_xlsx.py
Парсит .xlsx из Ozon Seller (аналитика по товарам) → SQLite.
Берёт самый свежий файл из downloads/.
Идемпотентный: повторный запуск на том же файле не создаёт дублей.
"""
import os
import re
import sys
import glob
import math
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = "ozon.db"
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_APP_DIR)
DOWNLOADS_DIR = os.path.join(_ROOT_DIR, "downloads")

# Индексы колонок (0-based) — соответствуют структуре отчёта Ozon
COL = {
    'name': 0,
    'category_l1': 1,
    'category_l2': 2,
    'category_l3': 3,
    'brand': 4,
    'model': 5,
    'scheme': 6,
    'sku': 7,
    'offer_id': 8,
    'date': 9,
    'abc_revenue': 10,
    'abc_orders': 11,
    'revenue': 12,
    'revenue_max_price': 13,
    'revenue_share': 14,
    'position_search': 15,
    'views_total': 16,
    'visitors_total': 17,
    'conv_view_to_order': 18,
    'views_search': 19,
    'visitors_search': 20,
    'conv_search_to_cart': 21,
    'cart_adds_search': 22,
    'conv_search_to_pdp': 23,
    'pdp_visits': 24,
    'pdp_visitors': 25,
    'conv_pdp_to_cart': 26,
    'cart_adds_pdp': 27,
    'conv_to_cart_total': 28,
    'cart_adds_total': 29,
    'conv_cart_to_order': 30,
    'orders_units': 31,
    'delivered': 32,
    'conv_order_to_purchase': 33,
    'purchased': 34,
    'cancelled': 35,
    'returned_by_return_date': 36,
    'returned_by_order_date': 37,
    'avg_price': 38,
    'discount_pct': 39,
    'price_index': 40,
    'days_in_promo': 41,
    'drr': 42,
    'days_with_ads': 43,
    'stock': 44,
    'reviews': 45,
    'rating': 46,
}

SKIP_VALUES = {'–', '-', '', None, 'None', 'nan'}
MAX_UINT32_PCT = 4294967295  # Ozon-спецзначение "не применимо"


# ---------------------------------------------------------------------------
# Парсеры значений
# ---------------------------------------------------------------------------

def to_money(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if math.isnan(v):
            return None
        return float(v)
    s = str(v).strip()
    if s in SKIP_VALUES:
        return None
    s = s.replace('₽', '').replace('\u00A0', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def to_percent(v):
    """'8,89%' → 0.0889"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if math.isnan(v):
            return None
        return float(v)
    s = str(v).strip()
    if s in SKIP_VALUES:
        return None
    s = s.replace('%', '').replace('\u00A0', '').replace(' ', '').replace(',', '.')
    try:
        n = float(s)
    except ValueError:
        return None
    # Ozon-спецзначение 4294967295% → не применимо
    if abs(n) >= MAX_UINT32_PCT:
        return None
    return n / 100.0


def to_int(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if math.isnan(v):
            return None
        return int(v)
    s = str(v).strip()
    if s in SKIP_VALUES:
        return None
    s = s.replace('\u00A0', '').replace(' ', '').replace(',', '.')
    try:
        return int(float(s))
    except ValueError:
        return None


def to_int_pair(v):
    """'1 из 1' → (1, 1); '0 из 17' → (0, 17); иначе (None, None)"""
    if v is None:
        return (None, None)
    s = str(v).strip()
    if s in SKIP_VALUES:
        return (None, None)
    m = re.match(r'(\d+)\s+из\s+(\d+)', s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (None, None)


def to_str(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip()
    if s in SKIP_VALUES:
        return None
    return s


def to_date_str(v):
    """Возвращает 'YYYY-MM-DD' или None."""
    if v is None:
        return None
    s = str(v).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    # Timestamp или другой формат
    try:
        return pd.to_datetime(v).strftime('%Y-%m-%d')
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Поиск файла и периода
# ---------------------------------------------------------------------------

def find_latest_xlsx(explicit=None):
    if not os.path.isdir(DOWNLOADS_DIR):
        print(f"[ERROR] Папка {DOWNLOADS_DIR} не найдена")
        sys.exit(1)
    files = glob.glob(os.path.join(DOWNLOADS_DIR, "*.xlsx"))
    if not files:
        print(f"[ERROR] В папке {DOWNLOADS_DIR} нет .xlsx")
        sys.exit(1)
    if explicit:
        # Ищем по имени (basename)
        matches = [f for f in files if os.path.basename(f) == explicit]
        if not matches:
            print(f"[ERROR] Файл {explicit} не найден в {DOWNLOADS_DIR}")
            sys.exit(1)
        return matches[0]
    return max(files, key=os.path.getmtime)


def parse_args():
    args = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            args["file"] = arg.split("=", 1)[1]
    return args


def extract_period(df_raw):
    """Ищет строку 'Период: DD.MM.YYYY – DD.MM.YYYY' в первых 5 строках."""
    for i in range(min(5, len(df_raw))):
        for v in df_raw.iloc[i]:
            s = str(v) if v is not None else ''
            if 'Период' in s:
                m = re.search(r'(\d{2}\.\d{2}\.\d{4})\s*[–-]\s*(\d{2}\.\d{2}\.\d{4})', s)
                if m:
                    d1 = datetime.strptime(m.group(1), '%d.%m.%Y').strftime('%Y-%m-%d')
                    d2 = datetime.strptime(m.group(2), '%d.%m.%Y').strftime('%Y-%m-%d')
                    return d1, d2
    return None, None


def find_data_start(df_raw):
    """Индекс первой строки с данными (после 'Итого и среднее')."""
    for i in range(min(30, len(df_raw))):
        for v in df_raw.iloc[i]:
            s = str(v).strip() if v is not None else ''
            if s.startswith('Итого и среднее'):
                return i + 1
    return 13  # fallback — по нашему знанию структуры


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------

def parse_file(path):
    print(f"Читаем: {path}")
    df_raw = pd.read_excel(path, sheet_name=0, header=None, engine='calamine')
    print(f"Прочитано строк: {len(df_raw)}, колонок: {len(df_raw.columns)}")

    if len(df_raw.columns) < 47:
        print(f"[WARN] Ожидалось 47 колонок, получено {len(df_raw.columns)}. Проверь структуру файла.")

    period_from, period_to = extract_period(df_raw)
    print(f"Период: {period_from} — {period_to}")

    start = find_data_start(df_raw)
    print(f"Данные начинаются со строки {start + 1} (индекс {start})")

    df = df_raw.iloc[start:].copy().reset_index(drop=True)
    print(f"Строк данных к обработке: {len(df)}")

    return df, period_from, period_to


def insert_rows(df, conn, period_from, period_to, source_file):
    cur = conn.cursor()
    inserted = 0
    skipped = 0
    products_seen = set()

    for idx, row in df.iterrows():
        sku = to_int(row[COL['sku']])
        date_str = to_date_str(row[COL['date']])

        if sku is None or date_str is None:
            skipped += 1
            continue

        days_promo_num, days_promo_total = to_int_pair(row[COL['days_in_promo']])
        days_ads_num, days_ads_total = to_int_pair(row[COL['days_with_ads']])

        try:
            cur.execute("""
                INSERT OR REPLACE INTO sales_daily (
                    sku, date,
                    abc_revenue, abc_orders,
                    revenue, revenue_max_price, revenue_share,
                    avg_price, discount_pct, drr,
                    position_search, price_index,
                    views_total, visitors_total,
                    views_search, visitors_search, conv_view_to_order,
                    pdp_visits, pdp_visitors, conv_search_to_pdp,
                    cart_adds_search, conv_search_to_cart,
                    cart_adds_pdp, conv_pdp_to_cart,
                    cart_adds_total, conv_to_cart_total,
                    orders_units, conv_cart_to_order,
                    delivered, purchased, conv_order_to_purchase,
                    cancelled, returned_by_return_date, returned_by_order_date,
                    days_in_promo, days_in_promo_total,
                    days_with_ads, days_with_ads_total,
                    stock, reviews, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sku, date_str,
                to_str(row[COL['abc_revenue']]),
                to_str(row[COL['abc_orders']]),
                to_money(row[COL['revenue']]),
                to_money(row[COL['revenue_max_price']]),
                to_percent(row[COL['revenue_share']]),
                to_money(row[COL['avg_price']]),
                to_percent(row[COL['discount_pct']]),
                to_percent(row[COL['drr']]),
                to_int(row[COL['position_search']]),
                to_str(row[COL['price_index']]),
                to_int(row[COL['views_total']]),
                to_int(row[COL['visitors_total']]),
                to_int(row[COL['views_search']]),
                to_int(row[COL['visitors_search']]),
                to_percent(row[COL['conv_view_to_order']]),
                to_int(row[COL['pdp_visits']]),
                to_int(row[COL['pdp_visitors']]),
                to_percent(row[COL['conv_search_to_pdp']]),
                to_int(row[COL['cart_adds_search']]),
                to_percent(row[COL['conv_search_to_cart']]),
                to_int(row[COL['cart_adds_pdp']]),
                to_percent(row[COL['conv_pdp_to_cart']]),
                to_int(row[COL['cart_adds_total']]),
                to_percent(row[COL['conv_to_cart_total']]),
                to_int(row[COL['orders_units']]),
                to_percent(row[COL['conv_cart_to_order']]),
                to_int(row[COL['delivered']]),
                to_int(row[COL['purchased']]),
                to_percent(row[COL['conv_order_to_purchase']]),
                to_int(row[COL['cancelled']]),
                to_int(row[COL['returned_by_return_date']]),
                to_int(row[COL['returned_by_order_date']]),
                days_promo_num, days_promo_total,
                days_ads_num, days_ads_total,
                to_int(row[COL['stock']]),
                to_int(row[COL['reviews']]),
                to_money(row[COL['rating']]),
            ))
            inserted += 1
        except Exception as e:
            print(f"[WARN] строка {idx}: {e}")
            skipped += 1
            continue

        # Обновляем products один раз на SKU
        if sku not in products_seen:
            products_seen.add(sku)
            try:
                cur.execute("""
                    INSERT INTO products (sku, offer_id, name, category_l1, category_l2,
                                          category_l3, brand, model, scheme,
                                          first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sku) DO UPDATE SET
                        offer_id    = COALESCE(excluded.offer_id, products.offer_id),
                        name        = COALESCE(excluded.name, products.name),
                        category_l1 = COALESCE(excluded.category_l1, products.category_l1),
                        category_l2 = COALESCE(excluded.category_l2, products.category_l2),
                        category_l3 = COALESCE(excluded.category_l3, products.category_l3),
                        brand       = COALESCE(excluded.brand, products.brand),
                        model       = COALESCE(excluded.model, products.model),
                        scheme      = COALESCE(excluded.scheme, products.scheme),
                        first_seen  = MIN(COALESCE(products.first_seen, excluded.first_seen), excluded.first_seen),
                        last_seen   = MAX(COALESCE(products.last_seen, excluded.last_seen), excluded.last_seen)
                """, (
                    sku,
                    to_str(row[COL['offer_id']]),
                    to_str(row[COL['name']]),
                    to_str(row[COL['category_l1']]),
                    to_str(row[COL['category_l2']]),
                    to_str(row[COL['category_l3']]),
                    to_str(row[COL['brand']]),
                    to_str(row[COL['model']]),
                    to_str(row[COL['scheme']]),
                    date_str, date_str,
                ))
            except Exception as e:
                print(f"[WARN] products для SKU {sku}: {e}")

    cur.execute("""
        INSERT INTO ingest_log (file_name, period_from, period_to, rows_parsed, parsed_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        source_file, period_from, period_to, inserted,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    ))

    conn.commit()
    return inserted, skipped


def print_stats(conn):
    print()
    cur = conn.execute("SELECT COUNT(*) FROM products")
    print(f"[OK] Товаров в products: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM sales_daily")
    print(f"[OK] Строк в sales_daily: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT MIN(date), MAX(date) FROM sales_daily")
    r = cur.fetchone()
    if r[0]:
        print(f"[OK] Период в БД: {r[0]} — {r[1]}")
    cur = conn.execute("SELECT COUNT(DISTINCT sku) FROM sales_daily")
    print(f"[OK] Уникальных SKU: {cur.fetchone()[0]}")


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] База не найдена: {DB_PATH}. Запусти init_db.py")
        sys.exit(1)

    args = parse_args()
    path = find_latest_xlsx(explicit=args.get("file"))
    print(f"Файл: {os.path.basename(path)}")
    df, p_from, p_to = parse_file(path)

    conn = sqlite3.connect(DB_PATH)
    try:
        inserted, skipped = insert_rows(df, conn, p_from, p_to, os.path.basename(path))
        print(f"\n[OK] Обработано: {inserted} строк")
        if skipped:
            print(f"[WARN] Пропущено: {skipped}")
        print_stats(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()