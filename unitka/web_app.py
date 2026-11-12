import streamlit as st
import ollama
import pandas as pd
import re
import os
import sys
import datetime
import subprocess
import sqlite3
import gspread
from google.oauth2.service_account import Credentials
from unitka.db import connect
from unitka import config

st.set_page_config(page_title="Пульт Ozon AI", page_icon="🤖", layout="wide")

# 1. РЕАЛЬНЫЙ ПЛАН ДЕЙСТВИЙ ИЗ GOOGLE SHEETS
@st.cache_data(ttl=300)
def load_action_plan():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(config.SHEET_ID)
        ws = sh.worksheet("План действий")
        rows = ws.get_all_values()
        
        plan = []
        # Пропускаем заголовки (строки 1 и 2), берем первые 5 задач
        for row in rows[2:7]:
            if len(row) >= 6:
                eff_str = row[5].replace('₽', '').replace(' ', '').replace(',', '.')
                try:
                    effect = float(eff_str)
                except:
                    effect = 0.0
                plan.append({"Задача": row[3], "Что делать": row[4], "Эффект": effect})
        return plan
    except Exception as e:
        return []

st.title("🤖 ИИ-Директор магазина VIVA HOME")

with st.sidebar:
    st.header("🎯 План действий на сегодня")
    plan = load_action_plan()
    if plan:
        total_loss = sum(item["Эффект"] for item in plan)
        st.metric(label="Общий убыток (Топ-5)", value=f"{total_loss:,.0f} ₽")
        st.divider()
        
        for i, item in enumerate(plan):
            with st.expander(f"{item['Задача']}"):
                st.write(f"**Действие:** {item['Что делать']}")
                st.write(f"**Потенциальная экономия:** {item['Эффект']:,.0f} ₽")
    else:
        st.info("План действий пуст или не загружен (проверьте VPN).")

    st.divider()
    
    st.header("📤 Загрузка данных Ozon")
    uploaded_file = st.file_uploader("Перетащите сюда файл .xlsx", type=["xlsx"])
    
    if uploaded_file is not None:
        save_dir = os.path.join(str(config.PROJECT), "app", "downloads")
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Файл {uploaded_file.name} сохранен!")
        
        if st.button("⚙️ Обработать этот файл"):
            with st.spinner("Обрабатываю Excel..."):
                result = subprocess.run(
                    [sys.executable, "-m", "unitka.load_sales_xlsx", "--file", file_path],
                    capture_output=True, text=True, cwd=str(config.PROJECT)
                )
                if result.returncode == 0:
                    st.success("Данные успешно загружены в базу!")
                    st.cache_data.clear()
                else:
                    st.error(f"Ошибка: {result.stderr}")

    st.info("💡 Спросите меня о чем-нибудь в чате справа!")

MODEL = "qwen2.5:7b" 

@st.cache_data(ttl=3600)
def get_db_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    schema = "Таблицы: \n"
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        schema += f"- {t} ({', '.join(cols)})\n"
    conn.close()
    return schema

# 3. БЕЗОПАСНЫЙ SQL
@st.cache_data(ttl=60, show_spinner=False)
def execute_sql(sql_query):
    try:
        clean_query = sql_query.strip().upper()
        if not (clean_query.startswith("SELECT") or clean_query.startswith("WITH")):
            return "Ошибка: Разрешены только запросы на чтение (SELECT)."
        
        if "DROP" in clean_query or "DELETE" in clean_query or "UPDATE" in clean_query or "INSERT" in clean_query:
             return "Ошибка: Изменение данных запрещено."

        db_path = str(config.DB_PATH)
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        
        conn.set_progress_handler(lambda: 0, 10000)
        
        cur = conn.cursor()
        cur.execute(sql_query)
        rows = cur.fetchmany(100)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        return pd.DataFrame(rows, columns=columns) if rows else "Данных не найдено."
    except Exception as e:
        return f"Ошибка SQL: {e}"

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "data" in msg:
            st.dataframe(msg["data"], use_container_width=True)
            if "date" in msg["data"].columns:
                try:
                    st.line_chart(msg["data"].set_index("date"))
                except Exception as e:
                    st.warning(f"Ошибка графика: {e}")

if prompt := st.chat_input("Например: Покажи выручку по месяцам..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    schema = get_db_schema()
    current_year = datetime.datetime.now().year
    
    # 5. ДИНАМИЧЕСКИЙ ГОД
    system_prompt = f"""Ты — SQL-робот для базы SQLite. Сейчас {current_year} год.
Вот ТОЧНЫЕ таблицы и их колонки. Используй ТОЛЬКО ИХ:

Таблица 1: abc_xyz
Колонки: sku (артикул), profit (прибыль), revenue (выручка).
ВАЖНО: В этой таблице НЕТ колонки date. Не фильтруй по датам!
Пример: SELECT sku, profit FROM abc_xyz WHERE profit < 0 ORDER BY profit ASC LIMIT 5

Таблица 2: monthly_reports
Колонки: period (месяц в формате '2026-10'), revenue (выручка).
ВАЖНО: Здесь НЕТ колонки sale_price или period_start! Используй только period и revenue.
Пример: SELECT period as date, revenue FROM monthly_reports WHERE period LIKE '2024-%' ORDER BY period

Таблица 3: realization_daily
Колонки: date (день в формате '2026-10-01'), sale_price (выручка), quantity.
Пример: SELECT date, SUM(sale_price) as revenue FROM realization_daily WHERE date LIKE '{current_year}-%' GROUP BY date ORDER BY date
"""

    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            response = ollama.chat(model=MODEL, messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            answer = response['message']['content'].strip()
            df_to_save = None

            sql_match = re.search(r'(?is)(SELECT\s+.*|WITH\s+.*)', answer)
            
            if sql_match:
                sql_query = sql_match.group(1).strip().rstrip(';')
                sql_query = sql_query.replace("DATE_FORMAT", "strftime").replace("DATE(", "date(")
                
                st.info(f"🔍 Выполняю запрос: {sql_query}")
                sql_result = execute_sql(sql_query)
                
                if isinstance(sql_result, pd.DataFrame):
                    df_to_save = sql_result
                    st.markdown("**Результат:**")
                    st.dataframe(sql_result, use_container_width=True)
                    
                    if "date" in sql_result.columns:
                        st.markdown("**График:**")
                        try:
                            st.line_chart(sql_result.set_index("date"))
                        except Exception as e:
                            st.warning(f"Ошибка графика: {e}")

                    data_str = sql_result.to_string(index=False)
                    response2 = ollama.chat(model=MODEL, messages=[
                        {"role": "system", "content": "Ты — финансовый директор. Напиши краткий вывод по данным."},
                        {"role": "user", "content": f"Запрос: {sql_query}\nДанные:\n{data_str}\nСделай вывод."}
                    ])
                    answer = response2['message']['content']
                else:
                    st.error(sql_result)
                    answer = "Не удалось получить данные. Попробуйте переформулировать."
            
            st.markdown(answer)

            msg_data = {"role": "assistant", "content": answer}
            if df_to_save is not None:
                msg_data["data"] = df_to_save
            st.session_state.messages.append(msg_data)