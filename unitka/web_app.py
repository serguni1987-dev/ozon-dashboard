import datetime
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread
import ollama
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from unitka import config

st.set_page_config(page_title="Пульт Ozon AI", layout="wide")
TABLES = {"abc_xyz", "monthly_reports", "realization_daily"}
FUNCTIONS = {"sum", "count", "avg", "min", "max", "round", "abs", "coalesce",
             "ifnull", "nullif", "date", "datetime", "strftime", "substr",
             "substring", "lower", "upper", "trim", "replace", "length"}
MODEL = config.AI_MODEL


def revision():
    paths = [Path(config.DB_PATH), Path(str(config.DB_PATH) + "-wal")]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                 if p.exists() else (str(p), 0, 0) for p in paths)


def open_readonly():
    uri = Path(config.DB_PATH).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10)


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
    lines = []
    with closing(open_readonly()) as conn:
        for table in sorted(TABLES):
            columns = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            if columns:
                lines.append(table + " (" + ", ".join(
                    f"{c[1]} {c[2]}" for c in columns) + ")")
    return "\n".join(lines)


def authorize(action, arg1, arg2, database, origin):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return (sqlite3.SQLITE_OK if database == "main" and arg1 in TABLES
                else sqlite3.SQLITE_DENY)
    if action == sqlite3.SQLITE_FUNCTION:
        return (sqlite3.SQLITE_OK if (arg2 or arg1 or "").lower() in FUNCTIONS
                else sqlite3.SQLITE_DENY)
    return sqlite3.SQLITE_DENY


@st.cache_data(ttl=60, max_entries=100, show_spinner=False)
def execute_sql(sql, db_revision):
    if not re.match(r"^(SELECT|WITH)\b", sql.strip(), re.I):
        raise ValueError("Разрешены только SELECT и WITH ... SELECT.")
    with closing(open_readonly()) as conn:
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(authorize)
        deadline = time.monotonic() + 5
        conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(101)
        if len(rows) > 100:
            raise ValueError("Больше 100 строк: уточните запрос или используйте LIMIT 100.")
        return pd.DataFrame(rows, columns=[c[0] for c in cursor.description])


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
    with st.expander("Диагностика: настоящая схема базы"):
        st.code(schema or "Разрешённые таблицы не найдены.", language="text")
except Exception as exc:
    st.error(f"Не удалось прочитать схему базы: {exc}")
    st.stop()

if question := st.chat_input("Например: покажи убыточные товары"):
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
            message["content"] = raw
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
