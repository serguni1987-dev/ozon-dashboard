import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from .db import connect
from .calc_taxes import build as build_taxes

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

def get_manual_inputs(sh):
    cash, ap = 0.0, 0.0
    try:
        ws = sh.worksheet("Ручной ввод")
        vals = ws.get_all_values()
        for row in vals:
            if len(row) < 2: continue
            key = row[0].strip().lower()
            val_str = row[1].replace(" ", "").replace(",", ".").strip()
            if not val_str or val_str == "значение": continue
            try: val = float(val_str)
            except: continue
            if "деньги" in key or "счет" in key: cash = val
            elif "кредиторка" in key or "поставщик" in key: ap = val
    except Exception:
        pass
    return cash, ap

def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    cash, ap = get_manual_inputs(sh)
    
    tax_data = build_taxes(2026) 
    real_tax = tax_data['tax_to_pay']
    total_contrib = tax_data['total_contrib']
    total_burden = real_tax + total_contrib

    conn = connect()
    cur = conn.cursor()

    now = datetime.now()
    months_ru = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    
    current_month_str = now.strftime('%Y-%m')
    current_month_name = months_ru[now.month - 1]
    
    prev_month_dt = (now.replace(day=1) - timedelta(days=1))
    prev_month_str = prev_month_dt.strftime('%Y-%m')
    prev_month_name = months_ru[prev_month_dt.month - 1]

    # --- 1. Сбор данных за месяц ---
    def get_month_stats(m_str):
        cur.execute("SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals WHERE date LIKE ?", (f"{m_str}-%",))
        rev = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions WHERE type = 'deduction' AND date LIKE ?", (f"{m_str}-%",))
        exp = cur.fetchone()[0]
        cur.execute("""
            SELECT SUM(m.quantity * c.cost_price) FROM monthly_realization_rows m
            LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON m.sku = c.sku
            WHERE m.month = ? AND m.is_return = 0
        """, (m_str,))
        cogs = cur.fetchone()[0] or 0.0
        
        profit = rev - cogs - exp
        margin = (profit / rev * 100) if rev > 0 else 0
        return {"rev": rev, "profit": profit, "margin": margin}

    cur_stats = get_month_stats(current_month_str)
    prev_stats = get_month_stats(prev_month_str)

    # --- 2. Сбор данных за ГОД (YTD) ---
    def get_ytd_stats(year_str):
        cur.execute("SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals WHERE date LIKE ?", (f"{year_str}-%",))
        rev = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions WHERE type = 'deduction' AND date LIKE ?", (f"{year_str}-%",))
        exp = cur.fetchone()[0]
        cur.execute("""
            SELECT SUM(m.quantity * c.cost_price) FROM monthly_realization_rows m
            LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON m.sku = c.sku
            WHERE m.month LIKE ? AND m.is_return = 0
        """, (f"{year_str}-%",))
        cogs = cur.fetchone()[0] or 0.0
        
        profit = rev - cogs - exp
        margin = (profit / rev * 100) if rev > 0 else 0
        return {"rev": rev, "profit": profit, "margin": margin}

    ytd_stats = get_ytd_stats(str(now.year))

    # --- 3. Дебиторка ---
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_transactions")
    acc = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_payouts")
    pay = cur.fetchone()[0]
    receivables = acc - pay

    # --- 4. Склад и Неликвид ---
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    cur_inv = 0.0
    non_liquid = 0.0
    top_skus = []
    if last_date:
        cur.execute("""
            SELECT SUM((s.fbo_present + s.fbs_present) * c.cost_price)
            FROM stock_daily s LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON s.sku = c.sku
            WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
        """, (last_date,))
        cur_inv = cur.fetchone()[0] or 0.0

        cur.execute("""
            SELECT s.sku, ((s.fbo_present + s.fbs_present) * c.cost_price) as val
            FROM stock_daily s LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON s.sku = c.sku
            WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
            AND s.sku NOT IN (SELECT sku FROM realization_daily WHERE date >= date(?, '-60 days') AND is_return = 0)
            ORDER BY val DESC LIMIT 3
        """, (last_date, last_date))
        top_skus = [f"SKU {r[0]} ({r[1]:,.0f} руб.)" for r in cur.fetchall() if r[0]]
        
        cur.execute("""
            SELECT SUM((s.fbo_present + s.fbs_present) * c.cost_price)
            FROM stock_daily s LEFT JOIN (SELECT sku, cost_price FROM product_cost_history WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)) c ON s.sku = c.sku
            WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
            AND s.sku NOT IN (SELECT sku FROM realization_daily WHERE date >= date(?, '-60 days') AND is_return = 0)
        """, (last_date, last_date))
        non_liquid = cur.fetchone()[0] or 0.0

    conn.close()

    # --- 5. ПЛАН СПАСЕНИЯ КАССЫ ---
    discount_rate = 0.30 # Скидка 30% при распродаже
    non_liquid_cash = non_liquid * (1 - discount_rate) # Сколько денег реально получим
    total_potential = cash + receivables + non_liquid_cash
    gap = total_potential - total_burden

    # --- 6. Логика рекомендаций ---
    recommendations = []
    
    # Анализ прибыли
    if cur_stats['rev'] > 0:
        active_name = current_month_name
        active_stats = cur_stats
    else:
        active_name = prev_month_name
        active_stats = prev_stats
    
    if active_stats['rev'] == 0:
        recommendations.append(("⚪ Нет данных о продажах", "В текущем и прошлом месяце нет загруженных продаж."))
    elif active_stats['profit'] > 0:
        status = "🟢 Бизнес прибыльный" if active_stats['margin'] > 20 else "🟡 Низкая маржинальность"
        recommendations.append((status, f"Прибыль за {active_name}: {active_stats['profit']:,.0f} руб. Маржа: {active_stats['margin']:.0f}%."))
    else:
        recommendations.append(("🔴 БИЗНЕС В УБЫТКЕ!", f"Убыток за {active_name}: {active_stats['profit']:,.0f} руб. Срочно проверьте расходы."))

    # Кассовый разрыв (с учетом плана спасения)
    if gap >= 0:
        recommendations.append(("🟢 Денег хватает на налоги", f"Даже с учетом скидки 30% на неликвид, потенциал ({total_potential:,.0f} руб.) покрывает налоги ({total_burden:,.0f} руб.)."))
    else:
        recommendations.append(("🔴 ВНИМАНИЕ: Кассовый разрыв!", f"Даже если продать неликвид со скидкой, не хватает {abs(gap):,.0f} руб. (Потенциал: {total_potential:,.0f} руб., Налоги: {total_burden:,.0f} руб.)"))

    # Неликвид
    if cur_inv > 0 and non_liquid > cur_inv * 0.2:
        recommendations.append(("🟡 Заморожены деньги в товаре", f"{non_liquid:,.0f} руб. без продаж >60 дней. Топ-3: {', '.join(top_skus)}."))
    else:
        recommendations.append(("🟢 Склад работает эффективно", "Нет критического объема неликвида."))

    # --- 7. Отрисовка ---
    try:
        ws = sh.worksheet("🚀 ДАШБОРД")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="🚀 ДАШБОРД", rows=60, cols=5)

    try:
        all_sheets = sh.worksheets()
        target_index = 0
        for i, sheet in enumerate(all_sheets):
            if "ИНСТРУКЦИЯ" in sheet.title:
                target_index = i + 1
                break
        new_order = [s for s in all_sheets if s.id != ws.id]
        new_order.insert(target_index, ws)
        sh.reorder_worksheets(new_order)
    except Exception:
        pass

    values = [
        ["ПУЛЬТ УПРАВЛЕНИЯ: ЧТО ДЕЛАТЬ СЕГОДНЯ?", "", "", ""],
        ["", "", "", ""],
        ["СТАТУС", "РЕКОМЕНДАЦИЯ", "", ""]
    ]
    for status, text in recommendations:
        values.append([status, text, "", ""])

    row_summary = 3 + len(recommendations) + 3
    values.append(["", "", "", ""])
    values.append(["СРАВНЕНИЕ ПОКАЗАТЕЛЕЙ", prev_month_name, current_month_name, f"ИТОГО ЗА {now.year} ГОД"])
    
    summary_data = [
        ["ВЫРУЧКА", prev_stats['rev'], cur_stats['rev'], ytd_stats['rev']],
        ["ПРИБЫЛЬ", prev_stats['profit'], cur_stats['profit'], ytd_stats['profit']],
        ["МАРЖА (%)", f"{prev_stats['margin']:.1f}%", f"{cur_stats['margin']:.1f}%", f"{ytd_stats['margin']:.1f}%"],
        ["---", "---", "---", "---"],
        ["ДЕНЬГИ И ДОЛГИ", "ЗНАЧЕНИЕ", "", ""],
        ["Дебиторка Ozon", receivables, "", ""],
        ["Деньги на счету", cash, "", ""],
        ["Налоги и взносы (ИТОГО)", total_burden, "", ""],
        ["---", "---", "---", "---"],
        ["СКЛАД", "ЗНАЧЕНИЕ", "", ""],
        ["Заморожено в неликвиде", non_liquid, "", ""]
    ]
    
    for row_data in summary_data:
        while len(row_data) < 4:
            row_data.append("")
        values.append(row_data)

    # Блок ПЛАН СПАСЕНИЯ КАССЫ
    row_rescue = len(values) + 2
    values.append(["", "", "", ""])
    values.append(["ПЛАН СПАСЕНИЯ КАССЫ (Если не хватает денег)", "СУММА", "", ""])
    values.append(["1. Деньги на счету", cash, "", ""])
    values.append(["2. Долг Ozon (скоро придет)", receivables, "", ""])
    values.append([f"3. Распродажа неликвида (со скидкой 30%)", non_liquid_cash, "", ""])
    values.append(["ИТОГО ПОТЕНЦИАЛ", total_potential, "", ""])
    values.append(["Требуется на налоги и взносы", total_burden, "", ""])
    
    if gap >= 0:
        values.append(["ПРОФИЦИТ (Все отлично)", gap, "", ""])
    else:
        values.append(["ДЕФИЦИТ (Нужны деньги)", gap, "", ""])

    ws.update(values=values, range_name="A1")

    format_requests = [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat"
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_summary, "endRowIndex": row_summary + 1, "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}},
            "fields": "userEnteredFormat"
        }},
        # План спасения заголовок
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_rescue, "endRowIndex": row_rescue + 1, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.8, "green": 0.9, "blue": 0.8}, "textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}},
            "fields": "userEnteredFormat"
        }},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}}
    ]

    for i, (status, text) in enumerate(recommendations):
        row_idx = 3 + i
        if "🔴" in status or "⚪" in status:
            bg_color = {"red": 0.98, "green": 0.89, "blue": 0.89}
        elif "🟡" in status:
            bg_color = {"red": 0.99, "green": 0.95, "blue": 0.85}
        else:
            bg_color = {"red": 0.9, "green": 0.96, "blue": 0.9}
        
        format_requests.append({
            "repeatCell": {
                "range": {"sheetId": ws.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"backgroundColor": bg_color, "wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.wrapStrategy"
            }
        })
        format_requests.append({
            "repeatCell": {
                "range": {"sheetId": ws.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat"
            }
        })

    # Форматирование разделов
    for i in range(len(summary_data)):
        row_idx = row_summary + 1 + i
        if "---" in summary_data[i][0]:
            format_requests.append({
                "repeatCell": {
                    "range": {"sheetId": ws.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 4},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": {"red": 0.3, "green": 0.3, "blue": 0.3}}, "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}},
                    "fields": "userEnteredFormat"
                }
            })

    # Форматирование чисел (сравнение)
    format_requests.append({
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_summary + 1, "endRowIndex": row_summary + 12, "startColumnIndex": 1, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat"
        }
    })

    # Форматирование чисел (план спасения)
    format_requests.append({
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_rescue + 2, "endRowIndex": row_rescue + 9, "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            "fields": "userEnteredFormat.numberFormat"
        }
    })
    
    # Выделяем ИТОГОВЫЕ строки в плане спасения
    format_requests.append({
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_rescue + 5, "endRowIndex": row_rescue + 6, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
            "fields": "userEnteredFormat"
        }
    })
    
    gap_color = {"red": 0.9, "green": 0.96, "blue": 0.9} if gap >= 0 else {"red": 0.98, "green": 0.89, "blue": 0.89}
    format_requests.append({
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_rescue + 7, "endRowIndex": row_rescue + 8, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": gap_color}},
            "fields": "userEnteredFormat"
        }
    })

    try:
        ws.unmerge_cells("A1:D1")
    except Exception:
        pass
    try:
        ws.merge_cells("A1:D1")
    except Exception:
        pass

    sh.batch_update({"requests": format_requests})

    print("Лист '🚀 ДАШБОРД' обновлен (добавлен План спасения кассы).")

if __name__ == '__main__':
    main()