import datetime
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import ollama
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from unitka import config
from unitka.ai_sql_safety import get_schema, read_query

st.set_page_config(page_title="Пульт Ozon AI", layout="wide")
MODEL = config.AI_MODEL


def revision():
    paths = [Path(config.DB_PATH), Path(str(config.DB_PATH) + "-wal")]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                 if p.exists() else (str(p), 0, 0) for p in paths)


@st.cache_data(ttl=300, max_entries=4)
def load_action_plan(sheet_id, credentials_path):
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    rows = gspread.authorize(creds).open_by_key(sheet_id).worksheet(
        "План действий").get_all_values()
    plan = []
    for row in rows[2:]:
        if len(row) < 6 or not row[3].strip():
            continue
        amount = re.sub(r"[\s₽]", "", row[5]).replace(",", ".")
        effect = float(amount)
        plan.append({"problem": row[3], "action": row[4], "effect": effect})
        if len(plan) == 5:
            break
    return plan


@st.cache_data(ttl=60, max_entries=8)
def get_db_schema(db_revision):
    return get_schema(config.DB_PATH)


@st.cache_data(ttl=60, max_entries=100, show_spinner=False)
def execute_sql(sql, db_revision):
    rows = read_query(config.DB_PATH, sql, max_rows=100, seconds=2.0)
    return pd.DataFrame(rows)


def render_message(message):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sql" in message:
            with st.expander("SQL и диагностика"):
                st.code(message["sql"], language="sql")
                if message.get("error"):
                    st.code(message["error"], language="text")
        if "data" in message:
            df = message["data"]
            st.dataframe(df, use_container_width=True)
            numeric = list(df.select_dtypes(include="number").columns)
            if "date" in df.columns and numeric:
                try:
                    chart = df[["date"] + numeric].copy()
                    chart["date"] = pd.to_datetime(chart["date"], errors="raise")
                    st.line_chart(chart.sort_values("date").set_index("date"))
                except Exception as exc:
                    st.warning(f"График не построен: {exc}")


st.title("ИИ-Директор магазина VIVA HOME")
st.caption("SQL ограничен проверяемыми колонками. Прибыль, налоги и цены этим чатом не подтверждаются.")
with st.sidebar:
    st.header("План действий")
    if st.button("Обновить данные и план"):
        load_action_plan.clear()
        get_db_schema.clear()
        execute_sql.clear()
    try:
        plan = load_action_plan(config.SHEET_ID, str(config.CREDENTIALS))
        if not plan:
            st.info("В листе нет задач.")
        else:
            st.metric("Сумма оценок эффекта (до 5 задач)",
                      f"{sum(t['effect'] for t in plan):,.0f} ₽")
            st.caption("Эффекты задач могут пересекаться; это не подтверждённый общий убыток.")
            for task in plan:
                with st.expander(task["problem"]):
                    st.write(task["action"])
                    st.write(f"Оценка эффекта: {task['effect']:,.0f} ₽")
    except Exception as exc:
        st.warning("Не удалось прочитать план действий.")
        with st.expander("Причина ошибки плана"):
            st.code(str(exc), language="text")

    st.divider()
    uploaded = st.file_uploader("Файл Ozon .xlsx", type=["xlsx"])
    if uploaded is not None and st.button("Обработать файл"):
        try:
            folder = Path(config.PROJECT) / "app" / "downloads"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (uuid.uuid4().hex + ".xlsx")
            path.write_bytes(uploaded.getbuffer())
            with st.spinner("Импорт Excel..."):
                result = subprocess.run(
                    [sys.executable, "-m", "unitka.load_sales_xlsx", "--file", str(path)],
                    cwd=str(config.PROJECT), capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
            if result.returncode:
                st.error(result.stderr or result.stdout or "Ошибка импорта.")
            else:
                execute_sql.clear()
                get_db_schema.clear()
                st.success("Импорт завершён. План в Sheets обновляется отдельно.")
        except Exception as exc:
            st.error(f"Ошибка импорта: {exc}")
    model = st.text_input("Модель Ollama", value=MODEL).strip()
    if st.button("Очистить историю чата"):
        st.session_state.messages = []

st.session_state.setdefault("messages", [])
for message in st.session_state.messages:
    render_message(message)

try:
    db_revision = revision()
    schema = get_db_schema(db_revision)
    with st.expander("Диагностика: разрешённая схема базы"):
        st.code(schema or "Разрешённые таблицы не найдены.", language="text")
except Exception as exc:
    st.error(f"Не удалось прочитать схему базы: {exc}")
    st.stop()

if question := st.chat_input("Например: покажи компоненты месячного отчёта за октябрь 2026"):
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    render_message(user_message)
    message = {"role": "assistant", "content": ""}
    try:
        if not schema:
            raise ValueError("В базе нет разрешённых таблиц.")
        today = datetime.datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()
        instruction = f"""Ты составляешь один запрос чтения SQLite. Сегодня {today}.
Реальная разрешённая схема:
{schema}
Используй только эти таблицы и реальные столбцы. Не придумывай поля.
Верни только SELECT или WITH ... SELECT, без Markdown и объяснений.
Не используй SELECT *. Для списка используй LIMIT не более 100.
Сохраняй явно указанный пользователем год, даже исторический.
Если год не указан, не добавляй произвольное ограничение текущим годом.
Для временного графика назови поле времени date и отсортируй по нему.
Не соединяй таблицы без известных ключей и гранулярности.
Не считай цену единицы выручкой без подтверждения; не угадывай бизнес-формулы.
Не используй таблицы или показатели, которых нет в схеме.
Числовые компоненты отчёта не являются подтверждённой чистой прибылью.
Не вычисляй прибыль, налоги, минимальные цены и финансовые рекомендации.
ABC содержит перекрывающиеся снимки: выбирай один period, не суммируй периоды.
Если смысла полей недостаточно, верни CANNOT_ANSWER: что нужно уточнить.
"""
        with st.spinner("Составляю запрос..."):
            response = ollama.chat(model=model, options={"temperature": 0}, messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": question},
            ])
        raw = response["message"]["content"].strip()
        sql = re.sub(r"^```(?:sql|sqlite)?\s*|\s*```$", "", raw, flags=re.I).strip()
        if not re.match(r"^(SELECT|WITH)\b", sql, re.I):
            message["content"] = (raw if raw.startswith("CANNOT_ANSWER") else
                                  "CANNOT_ANSWER: модель не вернула допустимый запрос или отказ.")
        else:
            message["sql"] = sql
            with st.spinner("Читаю данные..."):
                df = execute_sql(sql, db_revision)
            if df.empty:
                message["content"] = "По условиям запроса данных нет. Указанный год не заменялся."
            else:
                message["data"] = df
                message["content"] = "Результат запроса. Финансовый смысл показателей требует проверки."
    except Exception as exc:
        message["content"] = "Запрос не выполнен. Причина указана в диагностике."
        message.setdefault("sql", "Запрос не получен.")
        message["error"] = str(exc)
    st.session_state.messages.append(message)
    render_message(message)
