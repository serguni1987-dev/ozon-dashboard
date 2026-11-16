"""calc_unit_summary.py — юнит-сводка по трём периодам: год, прошлый месяц, текущий."""
import os, gspread
from datetime import datetime, date, timedelta
from google.oauth2.service_account import Credentials
from .db import connect
from .unit_core import sku_economics

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
from .config import SHEET_ID  # ID таблицы: app\.env → PULT_SHEET_ID


def _periods():
    today = date.today()
    year_from, year_to = f"{today.year}-01-01", today.strftime("%Y-%m-%d")
    prev_end = today.replace(day=1) - timedelta(days=1)
    prev_from = prev_end.replace(day=1).strftime("%Y-%m-%d")
    prev_to = prev_end.strftime("%Y-%m-%d")
    prev_month_name = prev_end.strftime("%B %Y")
    cur_from = today.replace(day=1).strftime("%Y-%m-%d")
    cur_to = today.strftime("%Y-%m-%d")
    cur_month_name = today.strftime("%B %Y")
    return [
        (f"ГОД {year_from} — {year_to}", year_from, year_to),
        (f"ПРОШЛЫЙ МЕСЯЦ ({prev_month_name}: {prev_from} — {prev_to})", prev_from, prev_to),
        (f"ТЕКУЩИЙ МЕСЯЦ ({cur_month_name}: {cur_from} — {cur_to}, идёт)", cur_from, cur_to),
    ]


def _load_offer_map(cur):
    offer_map = {}
    try:
        cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
        for r in cur.fetchall():
            offer_map[str(r[0])] = r[1]
    except Exception as e:
        print(f"Ошибка чтения sku_map: {e}")
    return offer_map


def build_period(conn, cur, offer_map, date_from, date_to):
    """Adapt SKU economics; public date_to remains inclusive."""
    end_exclusive = (date.fromisoformat(date_to) + timedelta(days=1)).isoformat()
    eco = sku_economics(cur, date_from, end_exclusive)
    items = []
    totals = {"revenue": 0.0, "cogs": 0.0, "exp": 0.0, "profit": 0.0}
    for sku, s in eco["skus"].items():
        revenue = s["income"]
        cogs = s["cogs"]
        exp = s["commission"] + s["svc_fixed"] + s["svc_pct"] + s["overhead"]
        profit = s["profit"]
        if revenue == 0 and cogs == 0 and exp == 0 and profit == 0:
            continue
        items.append({
            "offer_id": s.get("offer_id") or offer_map.get(str(sku), ""),
            "sku": sku, "revenue": revenue, "cogs": cogs, "exp": exp,
            "profit": profit, "min_price": None,
            "status": "Убыточный" if profit < 0 else ("Прибыльный" if profit > 0 else "Ноль"),
            "margin": profit / revenue * 100 if revenue != 0 else 0,
        })
        for key, value in (("revenue", revenue), ("cogs", cogs), ("exp", exp), ("profit", profit)):
            totals[key] += value
    items.sort(key=lambda item: item["profit"])
    return {"items": items, "totals": totals}


def build():
    conn = connect()
    try:
        cur = conn.cursor()
        offer_map = _load_offer_map(cur)
        _, d_from, d_to = _periods()[0]
        result = build_period(conn, cur, offer_map, d_from, d_to)
    finally:
        conn.close()
    return {
        "total_revenue": result["totals"]["revenue"],
        "total_cogs": result["totals"]["cogs"],
        "total_exp": result["totals"]["exp"],
        "total_profit": result["totals"]["profit"],
        "items": result["items"],
    }


def main():
    conn = connect()
    try:
        cur = conn.cursor()
        offer_map = _load_offer_map(cur)

        periods = _periods()
        blocks = []
        for title, d_from, d_to in periods:
            b = build_period(conn, cur, offer_map, d_from, d_to)
            blocks.append({'title': title, 'from': d_from, 'to': d_to, **b})
    finally:
        conn.close()

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet("Юнит-сводка")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Юнит-сводка", rows=500, cols=12)
    ws.clear()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = [[f"ЮНИТ-СВОДКА — обновлено {now_str}"]]
    fmt_marks = [(0, 'title')]

    # --- ВЕРХНИЙ БЛОК: КРАТКАЯ СВОДКА ---
    rows.append(["Период", "SKU", "Убыточных", "Выручка", "Себестоимость", "Расходы Ozon", "Прибыль", "Маржа %"])
    fmt_marks.append((len(rows) - 1, 'items_header'))
    
    for block in blocks:
        t = block['totals']
        items = block['items']
        margin_pct = (t['profit'] / t['revenue'] * 100) if t['revenue'] else 0
        n_neg = sum(1 for i in items if i['profit'] < 0)
        
        rows.append([
            block['title'].split('(')[0].strip(),
            len(items), n_neg,
            round(t['revenue'], 2), round(t['cogs'], 2),
            round(t['exp'], 2), round(t['profit'], 2),
            round(margin_pct, 1)
        ])
        fmt_marks.append((len(rows) - 1, 'totals_row'))
    
    rows.append([])
    rows.append([])

    # --- ДЕТАЛИЗАЦИЯ ПО ПЕРИОДАМ ---
    for block in blocks:
        t = block['totals']
        items = block['items']
        margin_pct = (t['profit'] / t['revenue'] * 100) if t['revenue'] else 0
        n_neg = sum(1 for i in items if i['profit'] < 0)

        rows.append([f"=== {block['title']} ==="])
        fmt_marks.append((len(rows) - 1, 'period'))
        rows.append([])

        rows.append(["Артикул", "SKU", "Выручка", "COGS", "Расходы Ozon", "Прибыль", "Мин. цена (не рассчитана)", "Маржа %", "Статус"])
        fmt_marks.append((len(rows) - 1, 'items_header'))

        if items:
            for it in items:
                rows.append([
                    it['offer_id'] or "", it['sku'],
                    round(it['revenue'], 2), round(it['cogs'], 2),
                    round(it['exp'], 2), round(it['profit'], 2),
                    "", round(it['margin'], 1),
                    it['status'],
                ])
        else:
            rows.append(["(нет данных за период)"])
        rows.append([])

    # Записываем всё
    ws.update(values=rows, range_name="A1")

    # === ФОРМАТИРОВАНИЕ ===
    reqs = []
    COLORS = {
        'title':    {"red": 0.18, "green": 0.33, "blue": 0.59},
        'period':   {"red": 0.9,  "green": 0.7,  "blue": 0.4},
        'items_header': {"red": 0.9, "green": 0.9, "blue": 0.9},
        'totals_row': {"red": 0.95, "green": 0.9, "blue": 0.8},
    }
    for row_idx, kind in fmt_marks:
        color = COLORS.get(kind)
        bold = kind in ('title', 'period', 'items_header', 'totals_row')
        cell_fmt = {"textFormat": {"bold": bold}}
        if color:
            cell_fmt["backgroundColor"] = color
        if kind == 'title':
            cell_fmt["horizontalAlignment"] = "CENTER"
            cell_fmt["textFormat"]["fontSize"] = 16
            cell_fmt["textFormat"]["foregroundColor"] = {"red": 1, "green": 1, "blue": 1}
        elif kind == 'period':
            cell_fmt["textFormat"]["fontSize"] = 14
        reqs.append({"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                      "startColumnIndex": 0, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": cell_fmt},
            "fields": "userEnteredFormat"
        }})

    for i, w in enumerate([150, 130, 110, 110, 110, 110, 100, 90, 110]):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": ws.id, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"
        }})

    if reqs:
        sh.batch_update({"requests": reqs})

    # Обновляем статус в НАСТРОЙКАХ
    try:
        ws_s = sh.worksheet("НАСТРОЙКИ")
        ws_s.update(values=[[
            "Юнит-сводка рассчитана", "—", now_str, "✅ Свежая"
        ]], range_name="E8:H8")
    except Exception as e:
        print(f"[!] Не удалось обновить НАСТРОЙКИ: {e}")

    print("=" * 60)
    print(f"ЮНИТ-СВОДКА обновлена ({now_str})")
    print("=" * 60)
    for block in blocks:
        t = block['totals']
        m = (t['profit'] / t['revenue'] * 100) if t['revenue'] else 0
        print(f"  {block['title']}")
        print(f"    SKU: {len(block['items'])} | Выручка: {t['revenue']:,.0f} ₽ | Прибыль: {t['profit']:,.0f} ₽ | Маржа: {m:.1f}%")
    print("=" * 60)


if __name__ == '__main__':
    main()