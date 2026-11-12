import os

code = '''"""unitka/web_app.py — Веб-интерфейс ИИ-Директора с графиками."""
import streamlit as st
import ollama
import pandas as pd
import re
from unitka.db import connect
from unitka import config

st.set_page_config(page_title="Пульт Ozon AI", page_icon="🤖", layout="wide")

@st.cache_data(ttl=3600)
def load_action_plan():
    return [
        {"Задача": "Поднять цену OCP013E4", "Эффект": 12530},
        {"Задача": "Пополнить остаток SM002180215", "Эффект": 3737},
        {"Задача": "Поднять цену SM002200220", "Эффект": 3236}
    ]

st.title("🤖 ИИ-Директор магазина VIVA HOME")

with st.sidebar:
    st.header("🎯 План действий на сегодня")
    plan = load_action_plan()
    total_loss = sum(item["Эффект"] for item in plan)
    st.metric(label="Общий убыток (Топ-3)", value=f"{total_loss:,.0f} ₽")
    st.divider()
    for i, item in enumerate(plan):
        with st.expander(f"{i+1}. {item['Задача']}"):
            st.write(f"**Потенциальная экономия:** {item['Эффект']:,.0f} ₽")
            st.button("✅ Сделано", key=f"btn_{i}")
    st.divider()
    st.info("💡 Спросите меня о чем-нибудь в чате справа!")

MODEL = "qwen2.5:3b-instruct" 

def get_db_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    schema = "Таблицы:\n"
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
                except:
                    pass

if prompt := st.chat_input("Например: Покажи выручку по месяцам..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    schema = get_db_schema()
    system_prompt = f"""Выдай только SQL-запрос для базы SQLite. Без текста и кавычек.
Используй ТОЛЬКО эти таблицы:
{schema}
Правила:
1. Выручка по месяцам: SELECT period as date, revenue FROM monthly_reports ORDER BY period
2. Выручка по дням: SELECT date, SUM(sale_price) as revenue FROM realization_daily GROUP BY date ORDER BY date
3. Пиши ТОЛЬКО сам запрос, начиная со слова SELECT. Ничего больше.
"""

    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            response = ollama.chat(model=MODEL, messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            answer = response['message']['content'].strip()
            df_to_save = None

            # Умный поиск SQL: ищем слово SELECT и всё, что после него
            sql_match = re.search(r'(?is)(SELECT\\s+.*)', answer)
            
            if sql_match:
                sql_query = sql_match.group(1).strip().rstrip(';')
                # Костыли для 3B модели
                sql_query = sql_query.replace("DATE_FORMAT", "strftime").replace("DATE(", "date(")
                
                st.info(f"🔍 Выполняю запрос: {sql_query}")
                sql_result = execute_sql(sql_query)
                
                if isinstance(sql_result, pd.DataFrame):
                    df_to_save = sql_result
                    st.markdown(f"**Результат:**")
                    st.dataframe(sql_result, use_container_width=True)
                    
                    if "date" in sql_result.columns:
                        st.markdown("**График:**")
                        try:
                            st.line_chart(sql_result.set_index("date"))
                        except Exception as e:
                            st.warning(f"Ошибка графика: {e}")

                    # Просим модель написать текстовый вывод
                    data_str = sql_result.to_string(index=False)
                    response2 = ollama.chat(model=MODEL, messages=[
                        {"role": "system", "content": "Ты — финансовый директор. Напиши краткий вывод по данным."},
                        {"role": "user", "content": f"Запрос: {sql_query}\\nДанные:\\n{data_str}\\nСделай вывод."}
                    ])
                    answer = response2['message']['content']
                else:
                    st.error(sql_result)
                    answer = "Не удалось получить данные. Попробуйте переформулировать."
            else:
                st.markdown(answer)

            msg_data = {"role": "assistant", "content": answer}
            if df_to_save is not None:
                msg_data["data"] = df_to_save
            st.session_state.messages.append(msg_data)
'''

path = r"C:\Users\sergu\Desktop\проект\unitka\web_app.py"
with open(path, "w", encoding="utf-8") as f:
    f.write(code)
print("УСПЕХ: web_app.py перезаписан чистым кодом!")