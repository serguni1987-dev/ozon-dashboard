"""Action-plan summary with separate metrics. No combined financial effect is computed."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import date

PLAN_SHEET = "План действий"
SUMMARY_SHEET = "Сводка ИИ"
DATA_START_ROW = 3
TIMEOUT_SEC = 180
MAX_WHY_WORDS = 16
KINDS = {
    "negative_margin": ("loss_30d", "оценка прямого убытка за 30 дней по задачам"),
    "price_below_min": ("loss_stock", "ценовой разрыв на остатке, не денежный убыток"),
    "out_of_stock": ("lost_revenue", "оценочная упущенная выручка, не прибыль"),
    "dead_stock": ("frozen", "капитал в товаре, не убыток"),
}
KIND_ORDER = ["loss_30d", "loss_stock", "lost_revenue", "frozen", "other"]
TIER = {kind: index for index, kind in enumerate(KIND_ORDER)}
WHY = {
    "negative_margin": "расчётная прямая маржа отрицательна, причины требуют проверки",
    "price_below_min": "цена ниже расчётного порога, исходные тарифы требуют проверки",
    "out_of_stock": "были доставки, но выгодность пополнения отдельно не подтверждена",
    "dead_stock": "товар занимает капитал, решение зависит от спроса и расходов",
}
DONE_MARKERS = ("✅", "выполн", "сделан", "готов", "закрыт", "отклон", "не актуал", "неактуал", "отмен")
_LEGACY_PREFIX = (("Цена", "price_below_min"), ("Нет в наличии", "out_of_stock"),
                  ("Неликвид", "dead_stock"), ("Маржинальность", "negative_margin"))


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    text = str(value).replace(" ", "").replace(" ", "")
    text = text.replace(" ", "").replace("₽", "").replace("−", "-").replace(",", ".").strip()
    try:
        number = float(text)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _rule_of(row):
    if len(row) >= 8 and str(row[7]).strip():
        return str(row[7]).strip()
    for prefix, rule in _LEGACY_PREFIX:
        if str(row[3]).startswith(prefix):
            return rule
    return ""


def tasks_from_rows(rows):
    tasks = []
    for source in rows[DATA_START_ROW:]:
        if not isinstance(source, (list, tuple)):
            continue
        row = [("" if v is None else v) for v in source] + [""] * 8
        if not str(row[2]).strip() or not str(row[3]).strip():
            continue
        rule = _rule_of(row)
        kind, label = KINDS.get(rule, ("other", "прочая оценка; методика не определена"))
        tasks.append(dict(severity=str(row[0]), offer_id=str(row[1]).strip(), sku=str(row[2]).strip(),
            problem=str(row[3]).strip(), action=str(row[4]).strip(), amount=_num(row[5]),
            status=str(row[6]).strip(), rule_id=rule, kind=kind, kind_label=label))
    return tasks


def tasks_from_sheet(sh):
    return tasks_from_rows(sh.worksheet(PLAN_SHEET).get_all_values())


def tasks_from_db(today=None):
    from .db import connect
    from . import calc_action_plan as cap
    conn = connect()
    try:
        tasks = cap.build_tasks(conn.cursor(), today=today)
    finally:
        conn.close()
    rows = [[], [], []] + [[cap.severity_label(t.severity), t.offer_id, t.sku, t.problem,
        t.action, t.money_impact, "", t.rule_id] for t in tasks]
    return tasks_from_rows(rows)


def is_open(task):
    return not any(marker in str(task.get("status", "")).lower() for marker in DONE_MARKERS)


def build_facts(tasks, top_n=3):
    top_n = max(1, min(int(top_n), 10))
    open_rows = [t for t in tasks if is_open(t)]
    groups = {}
    for source in open_rows:
        task = dict(source)
        task["sku"] = str(task.get("sku", "")).strip()
        rule = str(task.get("rule_id", "")).strip()
        task["kind"], task["kind_label"] = KINDS.get(rule, ("other", "прочая оценка; методика не определена"))
        task["amount"] = _num(task.get("amount"))
        key = (task["sku"], rule or str(task.get("problem", "")))
        groups.setdefault(key, []).append(task)
    eligible, conflicts, duplicates, unpriced = [], 0, 0, 0
    for group in groups.values():
        signatures = {(t["amount"], t["kind"], str(t.get("problem", "")), str(t.get("action", "")),
                       str(t.get("offer_id", ""))) for t in group}
        if len(signatures) > 1:
            conflicts += 1
            continue
        duplicates += len(group) - 1
        task = group[0]
        if not task["sku"] or task["amount"] is None or task["amount"] <= 0:
            unpriced += 1
            continue
        eligible.append(task)
    totals = {kind: math.fsum(t["amount"] for t in eligible if t["kind"] == kind) for kind in KIND_ORDER}
    ranked = sorted(eligible, key=lambda t: (TIER[t["kind"]], -t["amount"], t["sku"]))
    top, seen = [], set()
    for task in ranked:
        if task["sku"] not in seen:
            seen.add(task["sku"]); top.append(task)
        if len(top) == top_n:
            break
    return dict(date=date.today().strftime("%d.%m.%Y"), open_count=len(open_rows),
        done_count=sum(not is_open(t) for t in tasks), totals=totals, top=top,
        top_totals={kind: math.fsum(t["amount"] for t in top if t["kind"] == kind) for kind in KIND_ORDER},
        loss_total=None, top_sum=None, mixed_total_available=False,
        duplicate_rows_ignored=duplicates, conflicting_groups=conflicts, unpriced_groups=unpriced)


SYSTEM_CFO = ("Отвечай на русском, только JSON items с n и why для переданных задач. "
    "Не меняй порядок и действия. why — короткая причина до 16 слов без чисел, сумм и артикулов. "
    "Не складывай показатели, не делай вывод об общем убытке магазина.")
SYSTEM_MENTOR = ("Отвечай на русском, только JSON с text: краткая ремарка по переданным действиям. "
    "Без чисел, сумм, процентов и артикулов. Не добавляй действия и не утверждай общий убыток. "
    "Не складывай разнородные показатели. Все суммы и действия отдельно выведет программа.")
SCHEMA_MENTOR = {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}


def _schema_cfo(n):
    return {"type":"object","properties":{"items":{"type":"array","minItems":n,"maxItems":n,
        "items":{"type":"object","properties":{"n":{"type":"integer"},"why":{"type":"string"}},
                 "required":["n","why"]}}},"required":["items"]}


def ask_model(system, payload, schema, model, num_predict=220):
    import requests
    host = (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    body = dict(model=model, stream=False, format=schema,
        options=dict(temperature=0, seed=1, num_predict=num_predict),
        messages=[dict(role="system",content=system),dict(role="user",content=json.dumps(payload,ensure_ascii=False))])
    try:
        response = requests.post(host + "/api/chat", json=body, timeout=TIMEOUT_SEC)
        if response.status_code != 200:
            return None, f"Ollama: HTTP {response.status_code}"
        result = json.loads(response.json()["message"]["content"])
        return (result, "") if isinstance(result, dict) else (None, "Ответ модели не является объектом")
    except Exception as exc:
        return None, f"Модель недоступна или ответ не разобран: {type(exc).__name__}"


def _numbers(text):
    return set(re.findall(r"\d+", str(text)))


def _has_foreign(text):
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def why_from_model(facts, model):
    if not facts["top"]:
        return {}, ""
    payload = {"tasks":[dict(n=i+1, problem=t["problem"], action=t["action"], kind=t["kind_label"])
                         for i,t in enumerate(facts["top"])]}
    data, error = ask_model(SYSTEM_CFO,payload,_schema_cfo(len(facts["top"])),model)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {}, error or "Некорректный формат пояснений"
    accepted = {}
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        n, text = item.get("n"), _clean(item.get("why"))
        if (isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=len(facts["top"])
                or n in accepted or not text or len(text.split())>MAX_WHY_WORDS
                or _numbers(text) or _has_foreign(text)):
            continue
        accepted[n] = text
    return accepted, "Пояснения модели не являются проверенным финансовым выводом"


def mentor_from_model(facts, model):
    payload = {"tasks":[dict(problem=t["problem"],action=t["action"],kind=t["kind_label"]) for t in facts["top"]]}
    data,error = ask_model(SYSTEM_MENTOR,payload,SCHEMA_MENTOR,model,num_predict=320)
    text = _clean(data.get("text")) if isinstance(data,dict) else ""
    if (not text or len(text)>600 or _numbers(text) or _has_foreign(text)
            or re.search(r"(?i)под угрозой|потеряли|общий убыток|общая сумма|итого",text)):
        return "", error or "Комментарий модели отклонён; используется шаблон"
    return text, "Проверен формат, но не достоверность смысла комментария"


def fmt(value):
    return f"{value:,.0f}".replace(","," ") + " ₽"


def _totals_lines(facts):
    labels = dict(KINDS.values())
    labels["other"] = "прочие оценки с неустановленной методикой"
    lines = [f"{labels[k].capitalize()}: {fmt(facts['totals'][k])}." for k in KIND_ORDER if facts["totals"][k]>0]
    lines.append("Показатели не складываются: различаются периоды и экономический смысл; возможны пересечения по SKU.")
    lines.append("Это сводка задач, не P&L магазина. Свежесть и полнота исходного плана отдельно не подтверждены.")
    if facts["duplicate_rows_ignored"] or facts["conflicting_groups"] or facts["unpriced_groups"]:
        lines.append(f"Проверка строк: повторов исключено {facts['duplicate_rows_ignored']}; "
            f"конфликтных групп {facts['conflicting_groups']}; без положительной корректной суммы {facts['unpriced_groups']}.")
    return lines


def render_cfo(facts, why=None):
    lines = [f"ФИНДИРЕКТОР · {facts['date']} · открытых строк плана: {facts['open_count']}"] + _totals_lines(facts)
    if not facts["top"]:
        lines.append("Нет задач с пригодной положительной суммой для топа. Это не означает, что план выполнен или магазин без убытков.")
    else:
        lines.append(f"ТОП-{len(facts['top'])} ДЛЯ ПРОВЕРКИ:")
        for i,t in enumerate(facts["top"],1):
            lines.append(f"{i}. {t['offer_id'] or t['sku']} — {t['action']} · {fmt(t['amount'])} ({t['kind_label']}).")
            lines.append(t["problem"])
            reason = (why or {}).get(i) or WHY.get(t["rule_id"],"")
            if reason:
                lines.append("Пояснение: " + reason)
        lines.append("В топе не более одной задачи на SKU; остальные правила по тому же товару нужно просмотреть в плане.")
    return "\n".join(lines)


def render_mentor(facts, text=""):
    lines = [f"НАСТАВНИК · {facts['date']}"] + _totals_lines(facts)
    if facts["top"]:
        t = facts["top"][0]
        lines.append(f"Начните с проверки товара {t['offer_id'] or t['sku']}: {t['action']}. "
                     f"Показатель задачи: {fmt(t['amount'])} ({t['kind_label']}).")
    else:
        lines.append("Нет подходящих оценок для топа; выполнение плана этим не подтверждено.")
    if text:
        lines.append("Комментарий модели (смысл не верифицирован): " + text)
    return "\n".join(lines)


def write_summary(sh, text, mode, model_note):
    import gspread
    try:
        ws = sh.worksheet(SUMMARY_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SUMMARY_SHEET,rows=40,cols=2)
    rows = [[line] for line in text.splitlines()] + [[""],[f"Режим: {mode}. {model_note}"]]
    ws.clear(); ws.update(values=rows,range_name="A1",value_input_option="RAW")


def main():
    from . import config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=["cfo","mentor"],default="cfo")
    parser.add_argument("--local",action="store_true")
    parser.add_argument("--no-ai",action="store_true")
    parser.add_argument("--explain",action="store_true")
    parser.add_argument("--write",action="store_true")
    parser.add_argument("--top",type=int,default=3)
    parser.add_argument("--model",default=config.AI_MODEL)
    args = parser.parse_args()
    if args.local and args.write:
        parser.error("--local cannot be combined with --write")
    sh = None
    if args.local:
        tasks = tasks_from_db()
    else:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_file(str(config.CREDENTIALS),scopes=scopes)
        sh = gspread.authorize(credentials).open_by_key(config.SHEET_ID)
        tasks = tasks_from_sheet(sh)
    facts = build_facts(tasks,args.top)
    note = "Все суммы посчитаны программой по отдельным видам; общий эффект не рассчитывается."
    if args.mode == "cfo":
        why = {}
        if args.explain and not args.no_ai and facts["top"]:
            why,error = why_from_model(facts,args.model); note += " " + error
        text = render_cfo(facts,why)
    else:
        comment = ""
        if not args.no_ai and facts["top"]:
            comment,error = mentor_from_model(facts,args.model); note += " " + error
        text = render_mentor(facts,comment)
    print(text); print("[" + note + "]")
    if args.write:
        write_summary(sh,text,args.mode,note)


if __name__ == "__main__":
    main()
