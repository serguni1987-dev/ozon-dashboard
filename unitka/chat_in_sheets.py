"""unitka/chat_in_sheets.py — Чат с Оламой в Google Таблице (с историей)."""
import time
import datetime
import gspread
from google.oauth2.service_account import Credentials
from ollama import chat
from . import config
from .db import connect

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CHAT_SHEET = "Чат с ИИ"
MODEL = "qwen2.5:3b-instruct"

def get_db_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    schema = "Таблицы в базе:\n"
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        schema += f"- {t} ({', '.join(cols)})\n"
    conn.close()
    return schema

def execute_sql(sql_query):
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(sql_query)
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return "Данных не найдено."
        result = "\n".join([str(dict(row)) for row in rows[:20]])
        return result
    except Exception as e:
        return f"Ошибка SQL: {e}"

def main():
    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(config.SHEET_ID)
    
    try:
        ws = sh.worksheet(CHAT_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=CHAT_SHEET, rows=100, cols=3)

    # Настраиваем шапку, если ее нет
    if ws.acell('A1').value != 'Дата':
        ws.update(values=[['Дата', 'Вопрос', 'Ответ ИИ']], range_name='A1:C1')
        ws.format('A1:C1', {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})
        # Делаем колонки пошире
        sh.batch_update({"requests": [
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 350}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 600}, "fields": "pixelSize"}}
        ]})

    print(f"Слушаю лист '{CHAT_SHEET}'... (Ctrl+C для выхода)")
    
    print("Загружаю контекст (схема БД, План действий)...")
    schema = get_db_schema()
    try:
        plan_ws = sh.worksheet("План действий")
        plan_data = plan_ws.get_all_values()
        plan_text = "\n".join([" | ".join(row) for row in plan_data[1:6]])
    except:
        plan_text = "План действий пуст."

    system_prompt = f"""Ты — ИИ-финансовый директор магазина VIVA HOME на Ozon. 
Сейчас ноябрь 2026 года. Все данные в базе за 2026 год.

СХЕМА БАЗЫ:
{schema}

ВАЖНЫЕ ПРАВИЛА:
1. Валовая выручка = SUM(seller_price + bonus + coinvestment) из realization_daily. Или колонка revenue из monthly_reports. (Например, за октябрь это 124 246). 
2. Если пользователь просит "выручку за вычетом возвратов" или "чистую выручку", используй sale_price. (Например, за октябрь это 63 504).
3. Если тебе нужны данные из БД, напиши СТРОГО в формате: [SQL] ТВОЙ_ЗАПРОС_ЗДЕСЬ
   Не пиши слова "Вот запрос", не используй ```sql. Только [SQL] и сам запрос на одной строке.
4. Если ты уже знаешь ответ (например, из Плана действий), отвечай кратко и по делу.
"""

    last_processed_row = 1 # Начинаем со 2-й строки (после шапки)

    while True:
        try:
            # Получаем все вопросы из колонки B (Вопрос)
            col_b = ws.col_values(2)
            
            # Если появилась новая строка с вопросом
            if len(col_b) > last_processed_row:
                current_row = len(col_b)
                question = col_b[current_row - 1] # -1 т.к. индексы в питоне с 0
                
                if question and question != "Вопрос":
                    print(f"\nНовый вопрос (строка {current_row}): {question}")
                    
                    # Ставим дату и "Думаю..."
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    ws.update_cell(current_row, 1, now_str)
                    ws.update_cell(current_row, 3, "🤔 Думаю...")
                    
                    # Отправляем в ИИ
                    response = chat(model=MODEL, messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question}
                    ])
                    answer = response['message']['content']
                    
                    # Если ИИ нужен SQL
                    if "[SQL]" in answer:
                        sql_query = answer.split("[SQL]")[1].split("\n")[0].strip()
                        print(f"ИИ запросил данные: {sql_query}")
                        sql_result = execute_sql(sql_query)
                        
                        response = chat(model=MODEL, messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": question},
                            {"role": "assistant", "content": f"Я выполнил SQL: {sql_query}. Вот результат:\n{sql_result}"},
                            {"role": "user", "content": "Теперь дай финальный ответ на основе этих данных."}
                        ])
                        answer = response['message']['content']
                    
                    # Записываем ответ в колонку C
                    ws.update_cell(current_row, 3, answer)
                    last_processed_row = current_row
                    print("Ответ записан в таблицу.")
                    
            time.sleep(2)
            
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()