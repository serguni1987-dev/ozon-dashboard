"""
sync_decisions.py — читает отметки «сделано» из Google Sheets,
добавляет решения в SQLite.
"""
import os
import sqlite3
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
CREDENTIALS = "credentials.json"
DB = "ozon.db"

COMMISSION_PCT = 0.0281
SERVICES_PCT   = 0.142
TAX_PCT        = 0.15

YES_VALUES = {"да", "yes", "+", "✓", "1", "true", "y"}


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    return gspread.authorize(creds)


def already_in_db(con, offer_id, action_text, created_date):
    """Проверяет, нет ли уже такого решения за последние 30 дней."""
    row = con.execute("""
        SELECT 1 FROM decisions
        WHERE offer_id = ? AND action_text = ? AND created_at >= ?
        LIMIT 1
    """, (offer_id, action_text, created_date)).fetchone()
    return row is not None


def snapshot(con, offer_id):
    """Снимок метрик SKU за 30 дней."""
    prod = con.execute(
        "SELECT sku, cost_price FROM products WHERE offer_id = ?",
        (offer_id,)
    ).fetchone()
    if not prod:
        return None

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    agg = con.execute("""
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    """, (prod["sku"], date_from, max_date)).fetchone()

    price_row = con.execute("""
        SELECT AVG(avg_price) AS p FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ? AND orders_units > 0
    """, (prod["sku"], date_from, max_date)).fetchone()

    rev = agg["rev"] or 0
    orders = agg["orders"] or 0
    cost = (prod["cost_price"] or 0) * orders
    comm = rev * COMMISSION_PCT
    serv = rev * SERVICES_PCT
    pb = rev - cost - comm - serv
    tax = pb * TAX_PCT if pb > 0 else 0
    profit = pb - tax
    margin = profit / rev if rev else 0

    return {
        "rev": rev, "orders": orders,
        "views": agg["views"] or 0, "carts": agg["carts"] or 0,
        "price": price_row["p"] if price_row and price_row["p"] else 0,
        "profit": profit, "margin": margin,
    }


def main():
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ РЕШЕНИЙ ИЗ GOOGLE SHEETS")
    print("=" * 80)

    print("\n[1] Подключаюсь к Google Sheets...")
    client = get_client()
    sh = client.open_by_key(SHEET_ID)

    ws = sh.worksheet("ДЕЛАЙ")
    all_values = ws.get_all_values()
    print(f"  Строк на листе ДЕЛАЙ: {len(all_values)}")

    # Находим строку заголовка таблицы действий (там где "#", "Категория", ...)
    header_idx = None
    for i, row in enumerate(all_values):
        if row and row[0] == "#" and "Категория" in row:
            header_idx = i
            break

    if header_idx is None:
        print("  [WARN] Не нашёл заголовок таблицы действий. Ожидаю строку с '#', 'Категория', ...")
        return

    header = all_values[header_idx]
    print(f"  Заголовок (строка {header_idx+1}): {header}")

    # Индексы колонок
    try:
        col_offer = header.index("Offer ID")
        col_action = header.index("Что делать")
        col_effect = header.index("Эффект ₽/мес")
        col_done = header.index("Сделано?")
    except ValueError as e:
        print(f"  [ERROR] Не нашёл колонку: {e}")
        return

    print(f"  Колонки: offer={col_offer}, action={col_action}, effect={col_effect}, done={col_done}")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Дата для проверки дублей — 7 дней назад
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    added = 0
    skipped = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    review_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    for i, row in enumerate(all_values[header_idx + 1:], header_idx + 2):
        if len(row) <= max(col_offer, col_action, col_done):
            continue

        done_val = row[col_done].strip().lower()
        if done_val not in YES_VALUES:
            continue

        offer_id = row[col_offer].strip()
        action_text = row[col_action].strip()

        if not offer_id:
            continue

        # Проверка дублей
        if already_in_db(con, offer_id, action_text, week_ago):
            skipped += 1
            continue

        snap = snapshot(con, offer_id)
        if not snap:
            print(f"  [WARN] {offer_id}: не найден в products")
            skipped += 1
            continue

        con.execute("""
            INSERT INTO decisions
            (created_at, offer_id, category, action_text,
             revenue_before, profit_before, margin_before, orders_before,
             views_before, carts_before, price_before,
             status, review_at, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?)
        """, (
            now, offer_id, "",
            action_text,
            snap["rev"], snap["profit"], snap["margin"], snap["orders"],
            snap["views"], snap["carts"], snap["price"],
            review_at, f"из Google Sheets, строка {i}",
        ))
        added += 1
        print(f"  [ADD] {offer_id}: {action_text[:50]}")

    con.commit()
    con.close()

    print(f"\n[2] ИТОГИ:")
    print(f"  Добавлено решений: {added}")
    print(f"  Пропущено (дубли): {skipped}")

    # Убираем отметки, чтобы не сработали повторно
    if added > 0:
        for i, row in enumerate(all_values[header_idx + 1:], header_idx + 2):
            if len(row) > col_done and row[col_done].strip().lower() in YES_VALUES:
                ws.update_cell(i, col_done + 1, "")
        print(f"  Отметки в таблице очищены")

    print("=" * 80)


if __name__ == "__main__":
    main()
