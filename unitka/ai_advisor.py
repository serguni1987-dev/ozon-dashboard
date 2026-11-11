"""unitka/ai_advisor.py — утренняя сводка по листу «План действий».

    py -m unitka.ai_advisor                  режим «финдиректор»: суммы и топ-3 действия на сегодня
    py -m unitka.ai_advisor --mode mentor    режим «наставник»: 3–4 предложения для менеджера (пишет модель)
    py -m unitka.ai_advisor --local          без Google Sheets: задачи считаются из базы
    py -m unitka.ai_advisor --write          дополнительно записать сводку на лист «Сводка ИИ»
    py -m unitka.ai_advisor --top 5          сколько действий показывать (по умолчанию 3)
    py -m unitka.ai_advisor --explain        (опыт) причины в режиме «финдиректор» пишет модель
    py -m unitka.ai_advisor --no-ai          не обращаться к модели совсем

Как устроено и почему ответ всегда одного вида:
    1. Отбор, сортировку и ВСЕ суммы считает Python. Модель на 3 млрд параметров
       складывает с ошибками: на плане из 27 задач на 54 397 ₽ прежний промпт выдал
       «потеряли около 24 тысяч за сутки» и выбрал третью задачу вместо первой.
    2. Режим «финдиректор» модель не использует вовсе: это таблица из плана, а не текст.
       Причины — готовые формулировки по каждому правилу (WHY). При проверке модель
       qwen2.5:3b в двух случаях из семи написала неверную причину («низкая цена снижает
       спрос»), поэтому её пояснения включаются только флагом --explain.
    3. Режим «наставник»: модель получает уже посчитанные суммы и три задачи и только
       пересказывает их словами. Ответ — JSON по схеме, температура 0.
    4. Ответ модели проверяется: если в нём есть число, которого не было во входных
       данных, иероглифы или текст слишком длинный — берётся шаблон.
    5. Если Ollama не установлена или не отвечает, сводка всё равно выходит.

Модель задаётся в app\\.env: PULT_AI_MODEL (по умолчанию qwen2.5:3b-instruct).
Адрес Ollama: переменная OLLAMA_HOST (по умолчанию http://127.0.0.1:11434).
Модуль только читает лист «План действий»; пишет на лист «Сводка ИИ» только с --write.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date

from . import config

PLAN_SHEET = "План действий"
SUMMARY_SHEET = "Сводка ИИ"
DATA_START_ROW = 3               # заголовок, шапка, пустая строка — как пишет calc_action_plan
TIMEOUT_SEC = 180
MAX_WHY_WORDS = 16

# Что означает «Эффект, ₽» у каждого правила. Суммы разных видов не складываются:
# убыток — это деньги, упущенная выручка — оценка продаж, неликвид — замороженный капитал.
KINDS = {
    "negative_margin": ("loss_30d", "убыток за 30 дней"),
    "price_below_min": ("loss_stock", "потеря на остатке при текущей цене"),
    "out_of_stock": ("lost_revenue", "упущенная выручка за неделю"),
    "dead_stock": ("frozen", "заморожено в товаре"),
}
# Причина, по которой задача теряет деньги (режим «финдиректор»)
WHY = {
    "negative_margin": "за 30 дней товар продан дешевле, чем обошёлся с комиссией и логистикой",
    "price_below_min": "каждая продажа по этой цене — прямой убыток",
    "out_of_stock": "спрос есть, а продавать нечего",
    "dead_stock": "деньги лежат в товаре и не возвращаются в оборот",
}
KIND_ORDER = ["loss_30d", "loss_stock", "lost_revenue", "frozen", "other"]
# Порядок важности для топа: сначала прямые убытки (оба вида вместе, по сумме), затем
# упущенная выручка, затем неликвид. Внутри уровня — по убыванию суммы.
TIER = {"loss_30d": 0, "loss_stock": 0, "lost_revenue": 1, "frozen": 2, "other": 3}

# Статусы, с которыми задача в сводку не попадает (менеджер ставит их в колонке «Статус»)
DONE_MARKERS = ("✅", "выполн", "сделан", "готов", "закрыт", "отклон", "не актуал", "неактуал", "отмен")

_LEGACY_PREFIX = (
    ("Цена", "price_below_min"), ("Нет в наличии", "out_of_stock"),
    ("Неликвид", "dead_stock"), ("Маржинальность", "negative_margin"),
)


# ───────────────────────── данные ─────────────────────────

def _num(v) -> float:
    s = (str(v if v is not None else "").replace("\xa0", "").replace(" ", "").replace("₽", "")
         .replace("−", "-").replace(",", ".").strip())
    try:
        return float(s)
    except ValueError:
        return 0.0


def _rule_of(row: list) -> str:
    if len(row) >= 8 and str(row[7]).strip():
        return str(row[7]).strip()
    for prefix, rule_id in _LEGACY_PREFIX:
        if str(row[3]).startswith(prefix):
            return rule_id
    return ""


def tasks_from_rows(rows: list) -> list[dict]:
    """Строки листа «План действий» → задачи. Пустые строки и строки без SKU пропускаются."""
    out = []
    for row in rows[DATA_START_ROW:]:
        row = [("" if x is None else x) for x in row] + [""] * 8
        if not str(row[2]).strip() or not str(row[3]).strip():
            continue
        rule_id = _rule_of(row)
        kind, kind_label = KINDS.get(rule_id, ("other", "эффект"))
        out.append({
            "severity": str(row[0]), "offer_id": str(row[1]).strip(), "sku": str(row[2]).strip(),
            "problem": str(row[3]).strip(), "action": str(row[4]).strip(), "amount": _num(row[5]),
            "status": str(row[6]).strip(), "rule_id": rule_id, "kind": kind, "kind_label": kind_label,
        })
    return out


def tasks_from_sheet(sh) -> list[dict]:
    return tasks_from_rows(sh.worksheet(PLAN_SHEET).get_all_values())


def tasks_from_db(today: date | None = None) -> list[dict]:
    """Задачи напрямую из базы (режим --local): без статусов менеджера и без настроек с листа."""
    from .db import connect
    from . import calc_action_plan as cap
    conn = connect()
    tasks = cap.build_tasks(conn.cursor(), today=today)
    conn.close()
    rows = [[], [], []] + [[cap.severity_label(t.severity), t.offer_id, t.sku, t.problem, t.action,
                            t.money_impact, "", t.rule_id] for t in tasks]
    return tasks_from_rows(rows)


def is_open(task: dict) -> bool:
    status = task["status"].lower()
    return not any(m in status for m in DONE_MARKERS)


def build_facts(tasks: list[dict], top_n: int = 3) -> dict:
    """Всё, что в сводке является числом, считается здесь."""
    open_tasks = [t for t in tasks if is_open(t) and t["amount"] > 0]
    totals = {k: 0.0 for k in KIND_ORDER}
    for t in open_tasks:
        totals[t["kind"]] += t["amount"]
    ranked = sorted(open_tasks, key=lambda t: (TIER[t["kind"]], -t["amount"]))
    top, seen = [], set()
    for t in ranked:                       # одно действие на товар: вторая задача по тому же SKU
        if t["sku"] in seen:               # решается тем же действием
            continue
        seen.add(t["sku"])
        top.append(t)
        if len(top) >= top_n:
            break
    return {
        "date": date.today().strftime("%d.%m.%Y"),
        "open_count": len(open_tasks),
        "done_count": len([t for t in tasks if not is_open(t)]),
        "loss_total": totals["loss_30d"] + totals["loss_stock"],
        "totals": totals,
        "top": top,
        "top_sum": sum(t["amount"] for t in top),
    }


# ───────────────────────── модель ─────────────────────────

SYSTEM_CFO = (
    "Ты — финансовый директор магазина на Ozon. Отвечаешь только на русском языке и только JSON.\n"
    "Тебе дают задачи, которые уже выбраны и посчитаны программой. Для каждой задачи заполни поле why: "
    "одна фраза до 12 слов — чем эта проблема опасна для денег магазина, если её не решить.\n"
    "Правила:\n"
    "- количество и порядок задач не менять, поле n повторять как во входе;\n"
    "- в why нельзя писать числа, суммы, проценты и артикулы — их подставит программа;\n"
    "- нельзя повторять текст из полей problem и action и нельзя писать, что делать;\n"
    "- без приветствий и без слов «важно», «необходимо», «следует».\n"
    "Пример входа: {\"tasks\":[{\"n\":1,\"problem\":\"Неликвид: 4 шт лежат 90 дней без продаж\","
    "\"action\":\"Распродать или вывести\"}]}\n"
    "Пример ответа: {\"items\":[{\"n\":1,\"why\":\"деньги лежат в товаре и не возвращаются в оборот\"}]}"
)

SYSTEM_MENTOR = (
    "Ты — опытный наставник менеджера магазина на Ozon. Отвечаешь только на русском языке и только JSON.\n"
    "Тебе дают итоговые суммы и задачи на сегодня, уже выбранные и посчитанные. Напиши поле text: "
    "обращение к менеджеру из 3–4 коротких предложений простыми словами.\n"
    "Правила:\n"
    "- первое предложение — сколько денег под угрозой (поле loss_total);\n"
    "- второе — с какого товара начать (первая задача в списке) и что именно сделать;\n"
    "- названия полей и обозначения вроде «n = 1» в текст не переносить;\n"
    "- используй только числа и артикулы из входных данных, ничего не складывай и не округляй;\n"
    "- не придумывай встречи, звонки и сроки, которых нет во входе; без приветствий."
)


def _schema_cfo(n: int) -> dict:
    return {
        "type": "object",
        "properties": {"items": {
            "type": "array", "minItems": n, "maxItems": n,
            "items": {"type": "object",
                      "properties": {"n": {"type": "integer"}, "why": {"type": "string"}},
                      "required": ["n", "why"]},
        }},
        "required": ["items"],
    }


SCHEMA_MENTOR = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


def ask_model(system: str, payload: dict, schema: dict, model: str, num_predict: int = 220):
    """Запрос к Ollama по HTTP. Возвращает (dict | None, причина_отказа)."""
    import requests
    host = (os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    if not host.startswith("http"):
        host = "http://" + host
    body = {
        "model": model,
        "stream": False,
        "format": schema,                                    # ответ строго по JSON-схеме
        "options": {"temperature": 0, "seed": 1, "num_predict": num_predict},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    try:
        resp = requests.post(f"{host}/api/chat", json=body, timeout=TIMEOUT_SEC)
    except Exception as exc:  # noqa: BLE001
        return None, f"Ollama не отвечает ({type(exc).__name__}); запустите Ollama"
    if resp.status_code == 404:
        return None, f"модель {model} не установлена: ollama pull {model}"
    if resp.status_code != 200:
        return None, f"Ollama вернула код {resp.status_code}"
    try:
        return json.loads(resp.json()["message"]["content"]), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"ответ модели не разобран ({type(exc).__name__})"


def _numbers(text: str) -> set[str]:
    """Числа из текста в нормальном виде: «12 825 ₽», «12,825», «12825.0» → «12825»."""
    out = set()
    for raw in re.findall(r"\d[\d\s\u00a0\u202f.,]*", str(text)):
        digits = re.sub(r"[\s\u00a0\u202f]", "", raw).rstrip(".,")
        if re.fullmatch(r"\d{1,3}(,\d{3})+", digits):       # 12,825 — разделитель тысяч
            digits = digits.replace(",", "")
        digits = digits.replace(",", ".")
        if re.fullmatch(r"\d+\.0+", digits):
            digits = digits.split(".")[0]
        if digits:
            out.add(digits)
    return out


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().strip("«»\"'").rstrip(".").strip()


def _has_foreign(text: str) -> bool:
    """Иероглифы и прочие не-кириллические вставки — признак сбоя маленькой модели."""
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text))


def why_from_model(facts: dict, model: str):
    """Причины по топ-задачам от модели: {n: why}. Непрошедшие проверку пропускаются."""
    top = facts["top"]
    if not top:
        return {}, ""
    payload = {"tasks": [{"n": i + 1, "problem": t["problem"], "action": t["action"]}
                         for i, t in enumerate(top)]}
    data, err = ask_model(SYSTEM_CFO, payload, _schema_cfo(len(top)), model)
    if data is None:
        return {}, err
    out, rejected = {}, 0
    for item in data.get("items", []):
        n, why = item.get("n"), _clean(item.get("why"))
        if not isinstance(n, int) or not 1 <= n <= len(top) or n in out:
            continue
        allowed = _numbers(top[n - 1]["problem"] + " " + top[n - 1]["action"])
        if (not why or len(why.split()) > MAX_WHY_WORDS or _has_foreign(why)
                or not _numbers(why) <= allowed):
            rejected += 1
            continue
        out[n] = why[0].lower() + why[1:]
    note = f"пояснений модели отклонено проверкой: {rejected}" if rejected else ""
    return out, note


def mentor_from_model(facts: dict, model: str):
    payload = {
        "loss_total": fmt(facts["loss_total"]),
        "open_tasks": facts["open_count"],
        "tasks": [{"n": i + 1, "article": t["offer_id"] or t["sku"], "problem": t["problem"],
                   "action": t["action"], "amount": fmt(t["amount"]), "money": t["kind_label"]}
                  for i, t in enumerate(facts["top"])],
    }
    data, err = ask_model(SYSTEM_MENTOR, payload, SCHEMA_MENTOR, model, num_predict=320)
    if data is None:
        return "", err
    text = re.sub(r"\s+", " ", str(data.get("text") or "")).strip()
    allowed = _numbers(json.dumps(payload, ensure_ascii=False))
    for t in facts["top"]:                                  # цифры внутри артикула — не числа
        allowed |= _numbers(t["offer_id"]) | _numbers(t["sku"])
    extra = _numbers(text) - allowed
    if not text or _has_foreign(text):
        return "", "ответ модели пустой или не на русском"
    if extra:
        return "", "в ответе модели есть числа, которых нет в плане: " + ", ".join(sorted(extra))
    if len(re.findall(r"[.!?]+(?:\s|$)", text)) > 6:
        return "", "ответ модели длиннее 6 предложений"
    return text, ""


# ───────────────────────── текст ─────────────────────────

def fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " ₽"


def _totals_lines(facts: dict) -> list[str]:
    t = facts["totals"]
    lines = []
    if facts["loss_total"] > 0:
        parts = []
        if t["loss_30d"] > 0:
            parts.append(f"{fmt(t['loss_30d'])} убыток за 30 дней")
        if t["loss_stock"] > 0:
            parts.append(f"{fmt(t['loss_stock'])} потеряем на остатке при текущих ценах")
        lines.append(f"Убыток: {fmt(facts['loss_total'])} — " + ", ".join(parts) + ".")
    else:
        lines.append("Убыток: прямых убытков по открытым задачам нет.")
    extra = []
    if t["lost_revenue"] > 0:
        extra.append(f"упущенная выручка {fmt(t['lost_revenue'])}")
    if t["frozen"] > 0:
        extra.append(f"заморожено в неликвиде {fmt(t['frozen'])}")
    if t["other"] > 0:
        extra.append(f"прочее {fmt(t['other'])}")
    if extra:
        lines.append("Кроме того: " + ", ".join(extra) + ".")
    return lines


def render_cfo(facts: dict, why: dict | None = None) -> str:
    """why — причины от модели {номер: текст} (флаг --explain); без них берутся готовые из WHY."""
    why = dict(why or {})
    for i, t in enumerate(facts["top"], 1):
        if i not in why and t["rule_id"] in WHY:
            why[i] = WHY[t["rule_id"]]
    lines = [f"ФИНДИРЕКТОР · {facts['date']} · открытых задач: {facts['open_count']}"]
    if not facts["top"]:
        lines.append("Открытых задач с суммой нет. План действий выполнен.")
        return "\n".join(lines)
    lines += _totals_lines(facts)
    lines.append(f"ТОП-{len(facts['top'])} НА СЕГОДНЯ:")
    for i, t in enumerate(facts["top"], 1):
        lines.append(f"{i}. {t['offer_id'] or t['sku']} — {t['action']} · {fmt(t['amount'])} ({t['kind_label']})")
        lines.append(f"   {t['problem']}" + (f": {why[i]}." if i in why else "."))
    lines.append(f"Начать с №1. Сумма по топ-{len(facts['top'])}: {fmt(facts['top_sum'])}.")
    return "\n".join(lines)


def render_mentor(facts: dict, text: str = "") -> str:
    head = f"НАСТАВНИК · {facts['date']} · открытых задач: {facts['open_count']}"
    if not facts["top"]:
        return head + "\nОткрытых задач с суммой нет. План действий выполнен."
    if text:
        return head + "\n" + text
    t = facts["top"][0]
    body = (f"Под угрозой {fmt(facts['loss_total'])}. Начни с товара {t['offer_id'] or t['sku']}: "
            f"{t['action'][0].lower() + t['action'][1:]} — это {fmt(t['amount'])} ({t['kind_label']}). "
            f"Затем остальные задачи из плана по порядку.")
    return head + "\n" + body


def write_summary(sh, text: str, mode: str, model_note: str) -> None:
    import gspread
    try:
        ws = sh.worksheet(SUMMARY_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SUMMARY_SHEET, rows=40, cols=2)
    rows = [[line] for line in text.splitlines()]
    rows.append([""])
    rows.append([f"Режим: {mode}. {model_note}".strip()])
    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="RAW")


# ───────────────────────── запуск ─────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Сводка по плану действий: финдиректор или наставник")
    ap.add_argument("--mode", choices=["cfo", "mentor"], default="cfo")
    ap.add_argument("--local", action="store_true", help="без Google Sheets: задачи из базы")
    ap.add_argument("--no-ai", action="store_true", help="не обращаться к модели")
    ap.add_argument("--explain", action="store_true",
                    help="режим cfo: причины пишет модель (опыт; на маленькой модели бывают неверны)")
    ap.add_argument("--write", action="store_true", help=f"записать на лист «{SUMMARY_SHEET}»")
    ap.add_argument("--top", type=int, default=3, help="сколько действий показывать")
    ap.add_argument("--model", default=config.AI_MODEL, help="модель Ollama")
    args = ap.parse_args()

    sh = None
    if args.local:
        tasks = tasks_from_db()
    else:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=scopes)
        sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)
        try:
            tasks = tasks_from_sheet(sh)
        except gspread.WorksheetNotFound:
            raise SystemExit(f"Листа «{PLAN_SHEET}» нет. Сначала: py -m unitka.calc_action_plan")

    facts = build_facts(tasks, max(1, min(args.top, 10)))
    note = "Модель не использовалась: цифры и действия взяты из плана."
    if args.mode == "cfo":
        why = {}
        if args.explain and not args.no_ai and facts["top"]:
            why, err = why_from_model(facts, args.model)
            note = (f"Причины: {args.model}." + (f" ({err})" if err else "")) if why \
                else f"Причины из шаблона: {err}."
        text = render_cfo(facts, why)
    else:
        body = ""
        if not args.no_ai and facts["top"]:
            body, err = mentor_from_model(facts, args.model)
            note = f"Текст: {args.model}, числа сверены с планом." if body else f"Текст по шаблону: {err}."
        text = render_mentor(facts, body)

    print(text)
    print(f"[{note}]")
    if args.write and sh is not None:
        write_summary(sh, text, args.mode, note)
        print(f"Записано на лист «{SUMMARY_SHEET}».")


if __name__ == "__main__":
    main()
