"""unitka/load_sales_xlsx.py — загрузка воронки из xlsx Ozon."""
import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent / "app"
DOWNLOADS = APP_DIR / "downloads"

COLUMN_KEYS = {
    "sku": ["sku"],
    "offer_id": ["артикул продавца"],
    "name": ["товары"],
    "date": ["день"],
    "impressions": ["показы всего"],
    "views": ["посещения карточки"],
    "cart": ["добавления в корзину всего"],
    "orders": ["заказано товаров"],
    "buyouts": ["выкуплено товаров"],
    "position": ["позиция в поиске"],
    "drr": ["дрр"],
    "avg_price": ["средняя цена"],
    "price_index": ["индекс цен"],
    "discount_pct": ["скидка от медианной"],
    "reviews_count": ["отзывы"],
    "rating": ["рейтинг товара"],
}

def _find_col(headers, keys):
    for i, h in enumerate(headers):
        if not h:
            continue
        for key in keys:
            if key in h:
                return i
    return None

def _to_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace(" ", "").replace(",", ".").replace("%", "").strip()
    if s in ("", "–", "-", "nan"):
        return 0
    try:
        return float(s)
    except ValueError:
        return 0

def _parse_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def _read_xlsx_safe(path):
    try:
        df = pd.read_excel(path, engine="calamine", header=None)
        logger.info("Прочитано через calamine: %s строк, %s колонок", df.shape[0], df.shape[1])
        return df
    except Exception as e:
        logger.warning("calamine не смог: %s", e)
        df = pd.read_excel(path, engine="openpyxl", header=None)
        logger.info("Прочитано через openpyxl: %s строк", df.shape[0])
        return df

def _build_headers(df, max_header_rows=20):
    sku_row = None
    sku_col = None
    for i in range(min(max_header_rows, len(df))):
        row = df.iloc[i].tolist()
        for j, v in enumerate(row):
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if str(v).strip().lower() == "sku":
                    sku_row = i
                    sku_col = j
                    break
        if sku_row is not None:
            break

    if sku_row is None:
        return None, None, None

    data_start = None
    if sku_col is not None:
        for i in range(sku_row + 1, len(df)):
            v = df.iloc[i, sku_col]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                if s.replace(".", "").isdigit():
                    data_start = i
                    break
    if data_start is None:
        data_start = sku_row + 2

    # Собираем ВСЕ заголовки каждой колонки через пробел
    headers = []
    for j in range(df.shape[1]):
        parts = []
        for i in range(data_start):
            v = df.iloc[i, j]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                if s and s not in parts:
                    parts.append(s)
        header = " ".join(parts).lower().replace("\n", " ").replace("\r", " ")
        headers.append(header)

    return headers, data_start, sku_col

def load_file(path, date_str=None):
    if date_str is None:
        date_str = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")

    logger.info("Читаю файл: %s (дата файла %s)", path.name, date_str)
    df = _read_xlsx_safe(path)

    headers, data_start, sku_col = _build_headers(df)
    if headers is None:
        logger.error("Не нашёл заголовки")
        return 0

    logger.info("Заголовки найдены, данные с строки %s", data_start)

    cols = {}
    for field, keys in COLUMN_KEYS.items():
        idx = _find_col(headers, keys)
        cols[field] = idx
        if idx is not None and field in ("rating", "reviews_count", "avg_price", "price_index"):
            logger.info("Нашёл '%s' в колонке [%s] (%s)", field, idx, headers[idx][:60])

    if cols["sku"] is None:
        logger.error("Критично: не нашёл колонку SKU.")
        return 0

    conn = connect()
    cur = conn.cursor()
    saved = 0
    skipped = 0

    for i in range(data_start, len(df)):
        row_vals = df.iloc[i].tolist()
        sku_val = row_vals[cols["sku"]] if cols["sku"] < len(row_vals) else None
        if sku_val is None or (isinstance(sku_val, float) and pd.isna(sku_val)):
            skipped += 1
            continue

        sku = str(sku_val).strip()
        if sku.endswith(".0"):
            sku = sku[:-2]
        if not sku or not sku.replace(".", "").isdigit():
            skipped += 1
            continue

        def get(field):
            idx = cols.get(field)
            if idx is None or idx >= len(row_vals):
                return None
            v = row_vals[idx]
            if isinstance(v, float) and pd.isna(v):
                return None
            return v

        row_date = _parse_date(get("date")) or date_str

        cur.execute("""
            INSERT OR REPLACE INTO analytics_manual
            (date, sku, offer_id, name, impressions, views, cart, orders, buyouts,
             position, drr, avg_price, price_index, discount_pct, reviews_count, rating,
             source_file, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row_date, sku,
            str(get("offer_id")) if get("offer_id") else None,
            str(get("name")) if get("name") else None,
            int(_to_num(get("impressions"))),
            int(_to_num(get("views"))),
            int(_to_num(get("cart"))),
            int(_to_num(get("orders"))),
            int(_to_num(get("buyouts"))),
            _to_num(get("position")) or None,
            _to_num(get("drr")) or None,
            _to_num(get("avg_price")) or None,
            _to_num(get("price_index")) or None,
            _to_num(get("discount_pct")) or None,
            int(_to_num(get("reviews_count"))),
            _to_num(get("rating")) or None,
            path.name, datetime.now().isoformat(),
        ))
        saved += 1

    conn.commit()
    conn.close()
    logger.info("Сохранено строк: %s, пропущено: %s", saved, skipped)
    return saved

def main():
    parser = argparse.ArgumentParser(description="Загрузка воронки из xlsx Ozon")
    parser.add_argument("--file", help="Путь к конкретному .xlsx")
    parser.add_argument("--date", help="Дата среза YYYY-MM-DD")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            logger.error("Файл не найден: %s", path)
            return
        load_file(path, args.date)
        return

    if not DOWNLOADS.exists():
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        logger.warning("Папка %s создана.", DOWNLOADS)
        return

    files = sorted(DOWNLOADS.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        logger.warning("В %s нет .xlsx файлов.", DOWNLOADS)
        return

    path = files[0]
    load_file(path, args.date)

if __name__ == "__main__":
    main()
