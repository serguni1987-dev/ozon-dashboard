"""Google Sheets AI chat with restricted, read-only SQLite access."""
import datetime
import json
import time
from .ai_sql_safety import get_schema, read_query

CHAT_SHEET = "Чат с ИИ"
MODEL = "qwen2.5:3b-instruct"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_db_schema():
    from . import config
    return get_schema(config.DB_PATH)


def execute_sql(sql_query):
    from . import config
    try:
        rows = read_query(config.DB_PATH, sql_query, max_rows=20)
        return json.dumps(rows, ensure_ascii=False, default=str)
    except Exception as exc:
        return "SQL_NOT_EXECUTED: " + str(exc)


def system_prompt(schema):
    today = datetime.date.today().isoformat()
    return f"""Ты составляешь запрос чтения SQLite. Сегодня {today}.
Разрешённая схема:
{schema}
Для получения данных верни только [SQL] и один SELECT или WITH ... SELECT.
Используй только перечисленные таблицы и столбцы. Не используй SELECT *.
Не придумывай revenue или другие отсутствующие столбцы.
Сохраняй явно указанный год. Если год не задан, не подставляй его произвольно.
Числовые компоненты monthly_reports не являются подтверждённой чистой прибылью.
Смысл bonus и gross_commission_sum требует согласованной методики.
Не выводи прибыль, налоги, минимальные цены и финансовые рекомендации из этой схемы.
ABC содержит перекрывающиеся снимки: выбирай один period, не суммируй периоды.
Не соединяй таблицы без подтверждённых ключей и гранулярности.
Если данных или определения показателя недостаточно, верни CANNOT_ANSWER с причиной.
Не используй суммы из памяти или примеров; никаких фиксированных финансовых ответов.
"""


def main():
    import gspread
    from google.oauth2.service_account import Credentials
    from ollama import chat
    from . import config

    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)
    try:
        ws = sh.worksheet(CHAT_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=CHAT_SHEET, rows=100, cols=3)
    if ws.acell("A1").value != "Дата":
        ws.update(values=[["Дата", "Вопрос", "Ответ ИИ"]], range_name="A1:C1")

    print(f"Слушаю лист '{CHAT_SHEET}'. SQL: только ограниченное чтение.")
    last_processed_row = 1
    while True:
        try:
            questions = ws.col_values(2)
            if len(questions) > last_processed_row:
                current_row = len(questions)
                question = questions[current_row - 1]
                if question and question != "Вопрос":
                    ws.update_cell(current_row, 1, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
                    ws.update_cell(current_row, 3, "Проверяю данные...")
                    prompt = system_prompt(get_db_schema())
                    response = chat(model=MODEL, options={"temperature": 0}, messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": question},
                    ])
                    raw = response["message"]["content"].strip()
                    if raw.startswith("[SQL]"):
                        sql = raw[len("[SQL]"):].strip()
                        result = execute_sql(sql)
                        if result.startswith("SQL_NOT_EXECUTED:"):
                            answer = result
                        else:
                            answer = ("Результат ограниченного SQL-чтения. "
                                      "Финансовый смысл требует проверки.\nSQL: "
                                      + sql + "\n" + result)
                    elif raw.startswith("CANNOT_ANSWER"):
                        answer = raw
                    else:
                        answer = "CANNOT_ANSWER: модель не вернула допустимый запрос или отказ."
                    ws.update_cell(current_row, 3, answer)
                    last_processed_row = current_row
            time.sleep(2)
        except Exception as exc:
            print(f"Ошибка чата: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()
