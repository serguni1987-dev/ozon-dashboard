import sqlite3
import gspread
from google.oauth2.service_account import Credentials
from unitka import config
from ollama import chat
import os

MODEL = "qwen2.5:3b-instruct"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CRED = str(config.CREDENTIALS)

def get_plan_from_sheets():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(config.SHEET_ID)
    try:
        ws = sh.worksheet("План действий")
        rows = ws.get_all_values()
        # Берем первые 10 строк (самые важные)
        if len(rows) > 2:
            return rows[2:12] # Пропускаем заголовки
        return []
    except Exception as e:
        print(f"Ошибка чтения плана: {e}")
        return []

def main():
    print("Читаем План действий...")
    plan_rows = get_plan_from_sheets()
    
    if not plan_rows:
        print("План действий пуст. Сначала запустите calc_action_plan.")
        return

    # Формируем текст для ИИ
    text_plan = "\n".join([" | ".join(row) for row in plan_rows])
    
    prompt = f"""Ты — финансовый директор магазина на Ozon. 
Вот список проблем и задач на сегодня, отсортированный по размеру потерь:

{text_plan}

Напиши короткое утреннее обращение к менеджеру (3-4 предложения). 
Укажи общую сумму потерь, выдели самую критичную задачу и скажи, с чего начать.
Не используй сложные термины, пиши как опытный наставник.
"""
    print("Спрашиваем ИИ...")
    try:
        response = chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        print("\n" + "="*50)
        print("🤖 УТРЕННЯЯ СВОДКА ОТ ИИ:")
        print("="*50)
        print(response.message.content)
        print("="*50)
    except Exception as e:
        print(f"Ошибка ИИ: {e}. Проверьте, запущен ли Ollama (ollama serve).")

if __name__ == "__main__":
    main()