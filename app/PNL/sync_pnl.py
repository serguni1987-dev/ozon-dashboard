"""
sync_pnl.py - лист P&L: год по месяцам.

Ставка налога читается из листа НАСТРОЙКИ, ячейка B1.
Если лист/ячейка недоступны → DEFAULT_TAX_RATE.

COGS: через monthly_realization_rows: (доставлено − возвращено) × cost_price,
      количество возврата берётся из raw_json (return_commission.quantity),
      потому что в колонке quantity лежит только количество доставки.
Услуги Ozon: со знаком (минус — расход, плюс — компенсация/корректировка),
      чтобы итог расходов совпадал с ЛК «Экономика магазина» и Точкой.
Налог: УСН «доходы − расходы» (ставка из НАСТРОЙКИ!B1), минимум 1% от доходов.
      Помесячно — оценка; годовой расчёт — в листе «Налоги» (unitka.calc_taxes).
Заказы: из orders_created; если выгрузка аналитики Ozon (analytics_manual)
      показывает больше — берётся она (orders_created обновляется не каждый день).
"""
import os
import re
import sqlite3
import sys
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(APP_DIR, "ozon.db")
CREDENTIALS = os.path.join(APP_DIR, "credentials.json")

DEFAULT_TAX_RATE = 0.05
MIN_TAX_RATE = 0.01            # минимальный налог УСН Д−Р — 1% от доходов
FIXED_CONTRIB_YEAR = 57390.0   # фиксированные взносы ИП за 2026 (ст. 430 НК; 2025 было 53 658), делятся на 12 месяцев
SETTINGS_SHEET = "НАСТРОЙКИ"
SETTINGS_CELL = "B1"           # ставка, %
SETTINGS_REGIME = "B4"         # режим: «доходы − расходы» (Д-Р) или «доходы»
SETTINGS_CONTRIB = "B5"        # взносы ИП за год, ₽
REGIME_DR, REGIME_INCOME = "Д-Р", "Доходы"


def parse_regime(raw):
    t = str(raw or "").lower().replace("−", "-").replace("–", "-").replace(" ", "")
    if not t:
        return REGIME_DR
    if "расход" in t or "д-р" in t or t in ("др", "15", "15%"):
        return REGIME_DR
    if "доход" in t or t in ("6", "6%", "д"):
        return REGIME_INCOME
    return REGIME_DR

# ID таблицы — из unitka.config (app\.env → PULT_SHEET_ID). Если unitka недоступна — как раньше, из sheets_sync.py.
try:
    _project = os.path.dirname(APP_DIR)
    if _project not in sys.path:
        sys.path.insert(0, _project)
    from unitka.config import SHEET_ID
except Exception:  # noqa: BLE001
    _sync = open(os.path.join(APP_DIR, "sheets_sync.py"), encoding="utf-8").read()
    SHEET_ID = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', _sync).group(1)


CATEGORY_MAP = {
    # ═══ УСЛУГИ ДОСТАВКИ (Ozon) → Фулфилмент (наш) ═══
    # Логистика
    32: "Логистика",              # Logistic
    73: "Логистика",              # Shipment
    # Обработка, сборка
    16: "Обработка, сборка",      # Drop-Off
    17: "Обработка, сборка",      # Drop-Off Agent
    38: "Обработка, сборка",      # PackageCost
    39: "Обработка, сборка",      # PackingFee
    84: "Обработка, сборка",      # ItemPacking
    85: "Обработка, сборка",      # ItemSealing
    97: "Обработка, сборка",      # PackageUnitProcessing
    # Обратная логистика
    59: "Обратная логистика",     # ReturnFlowLogistic
    71: "Обратная логистика",     # SellerReturns
    53: "Обратная логистика",     # PreparingToReturn
    60: "Обратная логистика",     # ReturnStorageInTheWarehouse
    6:  "Обратная логистика",     # Cancellation
    9:  "Обратная логистика",     # ClientReturn
    40: "Обратная логистика",     # PartialReturn
    # Последняя миля
    28: "Последняя миля",         # LastMile
    30: "Последняя миля",         # LastMilePickUpPoint
    120: "Последняя миля",        # CourierPickUpByOzon
    121: "Последняя миля",        # CourierPickUpReinvoice

    # ═══ УСЛУГИ ПАРТНЁРОВ (Ozon) → Услуги агентов (наш) ═══
    1:  "Услуги агентов",         # Acquiring (Эквайринг)
    18: "Услуги агентов",         # EarlyPayment
    22: "Услуги агентов",         # Installment (Ozon Рассрочка)
    26: "Услуги агентов",         # KazakhstanBuyerInstallment
    29: "Услуги агентов",         # LastMileCourier (Доставка до места выдачи)
    45: "Услуги агентов",         # PickUpPointReturnAcceptance
    63: "Услуги агентов",         # RfbsDomesticAgentFee
    66: "Услуги агентов",         # RfbsGlobalAgentFee
    68: "Услуги агентов",         # RfbsServiceFee
    74: "Звёзды",                 # StarsMembership (Звёздные товары)
    79: "Услуги агентов",         # TemporaryPlacementsAgent
    98: "Услуги агентов",         # DeliveryToHandoverPlaceByOzon

    # ═══ ПРОДВИЖЕНИЕ И РЕКЛАМА (Ozon) → Маркетинг (наш) ═══
    41: "Реклама PPC",            # PayPerClick
    48: "Реклама PPC",            # PremiumCashbackIndividualPoints
    52: "Продвижение",            # PremiumSubscription
    54: "Продвижение",            # Promotion
    3:  "Бренд-комиссия",         # BrandCommission
    4:  "Бренд-комиссия",         # BrandPromotion
    5:  "Бренд-комиссия",         # BrandShelf
    47: "Отзывы",                 # PointsForReviews
    95: "Отзывы",                 # CustomerReviews
    96: "Отзывы",                 # AcceleratedReviewCollection
    70: "Отзывы",                 # SaleReview

    # ═══ УСЛУГИ FBO (Ozon) → Услуги FBO (наш) ═══
    46: "Услуги FBO",             # Placements (Размещение на складе)
    76: "Услуги FBO",             # StockInsurance
    12: "Услуги FBO",             # CrossDock (Кросс-докинг)
    77: "Услуги FBO",             # SupplyInbound (Обработка товара)

    # ═══ ДРУГИЕ УСЛУГИ И ШТРАФЫ (Ozon) → Другие услуги (наш) ═══
    14: "Другие услуги",          # DefectRate
    15: "Другие услуги",          # Disposal
    20: "Другие услуги",          # FlexiblePayments
    34: "Другие услуги",          # Marking
    35: "Другие услуги",          # Moderation
    89: "Другие услуги",          # DefectFineModeration
    90: "Другие услуги",          # DefectFineProhibitedGoods
    91: "Другие услуги",          # DefectFineCounterfeitGoods
    92: "Другие услуги",          # DefectFineComplaint
    93: "Другие услуги",          # DefectFineErrors
    94: "Другие услуги",          # DefectFineShipmentDelayRate

    # ═══ АНАЛИТИКА ═══
    125: "Аналитика",             # AnalyticsLite
    126: "Аналитика",             # AnalyticsPremium
    127: "Аналитика",             # AnalyticsPlus
    128: "Аналитика",             # AnalyticsPro

    # ═══ ПРОЧИЕ ═══
    57: "Прочие",                 # RealizationReportCorrection
    129: "Прочие",                # AnalyticsCorrection
    78: "Обработка, сборка",      # TemporaryPlacement
    25: "ItemCompensation",       # ItemCompensation
    0: "Другие услуги",           # fallback
}

MONTHS = ["янв", "фев", "мар", "апр", "май", "июн",
          "июл", "авг", "сен", "окт", "ноя", "дек"]
QUARTERS = ["1 кв", "2 кв", "3 кв", "4 кв"]


def get_tax_settings(sh):
    """{rate, regime, contrib} из листа НАСТРОЙКИ (B1, B4, B5). Нет листа/ячейки → значения по умолчанию."""
    st = {"rate": DEFAULT_TAX_RATE, "regime": REGIME_DR, "contrib": FIXED_CONTRIB_YEAR}
    try:
        ws = sh.worksheet(SETTINGS_SHEET)
        vals = ws.batch_get([SETTINGS_CELL, SETTINGS_REGIME, SETTINGS_CONTRIB])
        cell = lambda i: (vals[i][0][0] if vals[i] and vals[i][0] else "")  # noqa: E731
        raw = str(cell(0)).replace("%", "").replace(",", ".").strip()
        if raw:
            st["rate"] = float(raw) / 100.0
            print(f"[OK] Ставка налога из {SETTINGS_SHEET}!{SETTINGS_CELL}: {float(raw)}%")
        else:
            print(f"[i] {SETTINGS_SHEET}!{SETTINGS_CELL} пусто → {DEFAULT_TAX_RATE*100:.0f}%")
        st["regime"] = parse_regime(cell(1))
        print(f"[OK] Режим УСН из {SETTINGS_SHEET}!{SETTINGS_REGIME}: «{cell(1) or 'не задан'}» → {st['regime']}")
        raw = str(cell(2)).replace("₽", "").replace(" ", "").replace("\xa0", "").replace(",", ".").strip()
        if raw:
            st["contrib"] = float(raw)
        print(f"[OK] Взносы ИП за год: {st['contrib']:,.0f} ₽")
    except gspread.WorksheetNotFound:
        print(f"[!] Листа {SETTINGS_SHEET} нет → {DEFAULT_TAX_RATE*100:.0f}%, Д-Р, {FIXED_CONTRIB_YEAR:,.0f}")
    except Exception as e:
        print(f"[!] Не прочитал {SETTINGS_SHEET} ({e}) → {DEFAULT_TAX_RATE*100:.0f}%, Д-Р, {FIXED_CONTRIB_YEAR:,.0f}")
    return st


def make_verdict(label, pct_signed):
    lbl = label.strip().lower()

    if "фулфилмент" in lbl and ":" in label:
        pct = abs(pct_signed)
        if pct <= 8: return "✓ норма"
        if pct <= 12: return "⚠ высоко"
        return "!! критично"
    if "маркетинг" in lbl and ":" in label:
        pct = abs(pct_signed)
        if pct <= 10: return "✓ норма"
        if pct <= 15: return "⚠ высоко"
        return "!! критично"
    if "прямые" in lbl and "расход" in lbl:
        pct = abs(pct_signed)
        if pct <= 60: return "✓ норма"
        if pct <= 75: return "⚠ высоко"
        return "!! критично"

    if "валовая прибыль" in lbl or "чистая прибыль" in lbl or "ebitda" in lbl:
        if pct_signed >= 20: return "✓ норма"
        if pct_signed >= 10: return "⚠ средне"
        if pct_signed >= 0:  return "⚠ низко"
        return "!! убыток"
    if "доходы" in lbl and ":" not in label:
        return "✓ база"
    if "взносы" in lbl:
        return "✓ фикс. платёж"
    if "налог" in lbl:
        return "годовой расчёт — лист «Налоги»"
    if "себестоимость" in lbl and "оценка" in lbl:
        return "⚠ ноябрь — оценка"

    if "баллы" in lbl and "начислено" not in lbl:
        return "✓ компенсация"
    if "программы партнёров" in lbl:
        return "✓ партнёрские"

    pct = abs(pct_signed)
    if "комиссия" in lbl:
        if pct <= 45: return "✓ норма"
        if pct <= 55: return "⚠ высоко"
        return "!! критично"
    if "логистика" in lbl and "обратная" not in lbl:
        if pct <= 8: return "✓ норма"
        if pct <= 12: return "⚠ высоко"
        return "!! критично"
    if "себестоимость" in lbl:
        if pct <= 35: return "✓ норма"
        if pct <= 45: return "⚠ высоко"
        return "!! критично"
    if "реклама" in lbl:
        if pct <= 10: return "✓ норма"
        if pct <= 15: return "⚠ высоко"
        return "!! критично"
    if "fbo" in lbl:
        if pct <= 3: return "✓ норма"
        if pct <= 5: return "⚠ высоко"
        return "!! критично"
    if "другие услуги" in lbl or "прочие" in lbl:
        if pct <= 1: return "✓ норма"
        if pct <= 3: return "⚠ мелкие штрафы"
        return "!! штрафы"
    return ""


def f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def get_pnl_for_month(month, tax):
    tax_rate, regime, contrib_year = tax["rate"], tax["regime"], tax["contrib"]
    y, m = month.split("-")
    y, m = int(y), int(m)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    d1 = f"{y}-{m:02d}-01"
    d2 = f"{ny}-{nm:02d}-01"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Доходы из realization
    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    sale_price = f(r["slp"])
    bonus = f(r["bonus"])
    coinv = f(r["coinv"])
    commission = abs(f(r["comm"]))
    # 2. Если отчета нет (текущий месяц) — берем данные из ежедневных начислений (accruals)
    if sale_price == 0 and commission == 0:
        r_daily = con.execute("""
            SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
                   SUM(coinvestment) AS coinv, SUM(sale_commission) AS comm
            FROM accruals WHERE substr(date, 1, 7) = ?
        """, (month,)).fetchone()
        sale_price = f(r_daily["slp"])
        bonus = f(r_daily["bonus"])
        coinv = f(r_daily["coinv"])
        commission = abs(f(r_daily["comm"]))
        is_open_month = True
    else:
        is_open_month = False

    # Заказы (справочно) — из orders_created по дате создания (FBS+FBO)
    try:
        r2 = con.execute("""
            SELECT COUNT(*) AS orders FROM orders_created
            WHERE substr(created_at, 1, 7) = ?
        """, (month,)).fetchone()
        orders = int(r2["orders"] or 0)
    except sqlite3.OperationalError:
        # таблицы orders_created ещё нет — запусти PNL/_diag/fetch_orders_created.py
        orders = 0
    # orders_created обновляется не каждый день; выгрузка аналитики Ozon точнее
    try:
        r3 = con.execute("""
            SELECT COALESCE(SUM(orders), 0) FROM analytics_manual
            WHERE substr(date, 1, 7) = ?
        """, (month,)).fetchone()
        orders = max(orders, int(r3[0] or 0))
    except sqlite3.OperationalError:
        pass

    # Услуги из accruals_services
    cats = {}
    for row in con.execute("""
        SELECT type_id, SUM(amount) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (d1, d2)):
        cat = CATEGORY_MAP.get(row["type_id"], "Без категории")
        cats[cat] = cats.get(cat, 0) + f(row["total"])

    # ═══ СЕБЕСТОИМОСТЬ ═══
    # COGS = (доставлено − возвращено) × себестоимость на конец месяца.
    # В quantity хранится только количество доставки (delivery_commission.quantity);
    # количество возврата — в raw_json → return_commission.quantity. Строка «только
    # возврат» имеет quantity = 0, поэтому фильтр quantity > 0 здесь недопустим.
    cogs = 0.0
    cogs_estimated = False
    for r in con.execute("""
        SELECT sku,
               SUM(COALESCE(json_extract(raw_json, '$.delivery_commission.quantity'), quantity, 0)) AS q_buy,
               SUM(COALESCE(json_extract(raw_json, '$.return_commission.quantity'), 0)) AS q_ret
        FROM monthly_realization_rows
        WHERE month = ?
        GROUP BY sku
    """, (month,)):
        sku = r["sku"]
        qty_net = f(r["q_buy"]) - f(r["q_ret"])
        if qty_net == 0:
            continue

        r2 = con.execute("""
            SELECT cost_price FROM product_cost_history
            WHERE sku = ? AND date_from < ?
            ORDER BY date_from DESC, id DESC LIMIT 1
        """, (sku, d2)).fetchone()
        cost = f(r2[0]) if r2 and r2[0] else 0
        if cost == 0:
            continue

        cogs += cost * qty_net

    if is_open_month and cogs == 0:
        # Отчёта о реализации ещё нет — оценка: каждая строка начисления POSTING
        # с ценой > 0 = 1 проданная штука, с ценой < 0 = 1 возврат (по текущей себестоимости).
        r_est = con.execute("""
            SELECT COALESCE(SUM(CASE WHEN a.sale_price > 0 THEN c.cost_price
                                     WHEN a.sale_price < 0 THEN -c.cost_price ELSE 0 END), 0)
            FROM accruals a
            LEFT JOIN (SELECT sku, cost_price FROM product_cost_history
                       WHERE (sku, date_from) IN (SELECT sku, MAX(date_from)
                                                  FROM product_cost_history GROUP BY sku)) c
              ON a.sku = c.sku
            WHERE a.accrued_category = 'POSTING'
              AND substr(a.date, 1, 7) = ?
        """, (month,)).fetchone()
        cogs = f(r_est[0])
        cogs_estimated = cogs > 0

    con.close()

    revenue = sale_price + bonus + coinv
    # Услуги со знаком: расходы отрицательные, компенсации/корректировки положительные.
    # Раньше брался abs() по каждой категории, и, например, корректировка +332,67
    # за октябрь считалась расходом (Δ 665 ₽ с ЛК).
    services_signed = sum(cats.values())
    ads = -cats.get("Реклама PPC", 0)
    expenses_total = commission - services_signed          # = ЛК «Расходы», Точка
    expenses_no_ads = expenses_total - ads
    margin = revenue - expenses_total - cogs               # валовая прибыль
    contrib = contrib_year / 12.0                          # взносы ИП, 1/12 в месяц
    # Режим из НАСТРОЙКИ!B4. Помесячно — оценка, итог года — лист «Налоги».
    if regime == REGIME_INCOME:
        # УСН «доходы»: ставка × доходы, минус взносы ИП (ИП без работников — до нуля)
        tax_base = revenue
        tax = max(0.0, revenue * tax_rate - contrib) if revenue > 0 else 0.0
    else:
        # УСН «доходы − расходы»: база = доходы − все расходы − себестоимость − взносы;
        # минимальный налог 1% от доходов.
        tax_base = margin - contrib
        tax = max(tax_base * tax_rate, revenue * MIN_TAX_RATE) if revenue > 0 else 0.0
    net = margin - contrib - tax
    roi = (net / cogs * 100) if cogs else 0

    return {
        "orders": orders, "bonus": bonus, "revenue": revenue,
        "sale_price": sale_price, "coinv": coinv, "commission": commission,
        "cogs": cogs,
        "fulfil_logistics":  cats.get("Логистика", 0),
        "fulfil_reverse":    cats.get("Обратная логистика", 0),
        "fulfil_lastmile":   cats.get("Последняя миля", 0),
        "fulfil_processing": cats.get("Обработка, сборка", 0),
        "fulfil_total":     (cats.get("Логистика", 0) + cats.get("Обратная логистика", 0)
                              + cats.get("Последняя миля", 0) + cats.get("Обработка, сборка", 0)),
        "ppc":   cats.get("Реклама PPC", 0),
        "promo": cats.get("Продвижение", 0),
        "stars": cats.get("Звёзды", 0),
        "brand": cats.get("Бренд-комиссия", 0),
        "reviews": cats.get("Отзывы", 0),
        "market_total": (cats.get("Реклама PPC", 0) + cats.get("Продвижение", 0)
                         + cats.get("Звёзды", 0) + cats.get("Бренд-комиссия", 0)
                         + cats.get("Отзывы", 0)),
        "agents": cats.get("Услуги агентов", 0),
        "fbo": cats.get("Услуги FBO", 0),
        "other": cats.get("Другие услуги", 0),
        "misc": cats.get("Прочие", 0) + cats.get("ItemCompensation", 0), "ads": ads,
        "expenses_no_ads": expenses_no_ads,
        "expenses_total": expenses_total,
        "contrib": contrib, "cogs_estimated": cogs_estimated, "is_open_month": is_open_month,
        "margin": margin, "tax_base": tax_base, "tax": tax, "net": net, "roi": roi,
    }


def get_all_months():
    con = sqlite3.connect(DB)
    months = set()
    # 1. Берем месяцы, за которые есть закрытые отчеты
    for r in con.execute("SELECT DISTINCT month FROM monthly_realization_rows"):
        if r[0]: months.add(r[0])
    # 2. Берем месяцы из ежедневных начислений (чтобы видеть текущий месяц)
    for r in con.execute("SELECT DISTINCT substr(date, 1, 7) FROM accruals WHERE date IS NOT NULL"):
        if r[0]: months.add(r[0])
    con.close()
    return sorted(list(months))


def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def add_calc_formulas(rows):
    COL_YEAR = 2
    COL_PCT = 3
    COL_MONTH_1 = 4
    COL_Q1 = 16
    COL_VERDICT = 20

    def year_sum(row_idx):
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        r = row_idx + 1
        rows[row_idx][COL_YEAR - 1] = f"=SUM({c1}{r}:{c12}{r})"

    def quarter_sums(row_idx):
        r = row_idx + 1
        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(COL_MONTH_1 + m1 - 1)
            cB = col_letter(COL_MONTH_1 + m2 - 1)
            rows[row_idx][COL_Q1 + q - 1 - 1] = f"=SUM({cA}{r}:{cB}{r})"

    for ri in (36, 37, 38, 39):
        year_sum(ri); quarter_sums(ri)

    for m in range(1, 13):
        c = col_letter(COL_MONTH_1 + m - 1)
        idx = COL_MONTH_1 + m - 1 - 1
        rows[35][idx] = f"=SUM({c}37:{c}40)"
    year_sum(35); quarter_sums(35)

    # Операционные расходы в листе со знаком минус → EBITDA = валовая + опер. расходы
    # (раньше стояло «−», и взносы увеличивали прибыль).
    for idx in range(1, 19):
        col = col_letter(idx + 1)
        rows[41][idx] = f"={col}34+{col}36"
    for idx in range(1, 19):
        col = col_letter(idx + 1)
        rows[45][idx] = f"={col}42+{col}44"
    for idx in range(1, 19):
        col = col_letter(idx + 1)
        rows[46][idx] = f"=IF({col}32=0;0;-{col}46/{col}32*100)"

    # Строка 49 «Нераспределённая прибыль» = чистая прибыль + дивиденды (формулой,
    # чтобы учитывались ручные операционные расходы). Строка 50 «Накопленная прибыль»
    # — нарастающим итогом с января (раньше дублировала строку 49).
    for m in range(1, 13):
        col = col_letter(COL_MONTH_1 + m - 1)
        idx = COL_MONTH_1 + m - 1 - 1
        rows[48][idx] = f"={col}46+{col}48"
        rows[49][idx] = f"=SUM($D$49:{col}49)"
    rows[49][COL_YEAR - 1] = "=B49"

    # Колонка C («% от базы») для расчётных строк — всегда от годовых доходов B5,
    # а не сумма/разность процентов соседних строк.
    for r in (36, 42, 46, 49, 50):
        rows[r - 1][COL_PCT - 1] = f"=IF($B$5=0;0;B{r}/$B$5*100)"
    rows[46][COL_PCT - 1] = "=B47"   # ROI — тот же процент, что в B
    for q in range(1, 5):
        cB = col_letter(COL_MONTH_1 + q * 3 - 1)
        rows[49][COL_Q1 + q - 1 - 1] = f"=SUM($D$49:{cB}49)"


def build_table(year, tax):
    tax_rate, regime = tax["rate"], tax["regime"]
    all_months = [m for m in get_all_months() if m.startswith(str(year))]
    by_month = {m: get_pnl_for_month(m, tax) for m in all_months}

    COL_YEAR = 2
    COL_PCT = 3
    COL_MONTH_1 = 4
    COL_Q1 = 16
    COL_VERDICT = 20

    def mcol(mn):
        return COL_MONTH_1 + (mn - 1)

    def qcol(q):
        return COL_Q1 + (q - 1)

    rows = []
    rows.append(["Отчёт о прибылях и убытках OZON"] + [""] * 19)

    row2 = [""] * 20
    row2[1] = f"Всего за {year}"
    row2[2] = "% от базы"
    for i, name in enumerate(MONTHS):
        row2[mcol(i + 1) - 1] = name
    # Месяц без отчёта о реализации (текущий) помечаем — цифры по нему предварительные
    for m_str, data in by_month.items():
        if data.get("cogs_estimated") or data.get("is_open_month"):
            row2[mcol(int(m_str.split("-")[1])) - 1] = MONTHS[int(m_str.split("-")[1]) - 1] + " (идёт)"
    for i, name in enumerate(QUARTERS):
        row2[qcol(i + 1) - 1] = name
    row2[19] = "выводы"
    rows.append(row2)

    lines = [
        ("Заказы (справочно)", "orders"),
        ("Начислено баллов", "bonus"),
        ("Всего к начислению (Отчёт о реализации)", "revenue"),
        ("Сумма Отчёта о реализации", "sale_price"),
        ("", None),
        ("ДОХОДЫ", "revenue"),
        ("  Выручка за вычетом возвратов", "sale_price"),
        ("  Баллы за скидки", "bonus"),
        ("  Программы партнёров", "coinv"),
        ("  Компенсации", None),
        ("", None),
        ("Прямые (переменные) расходы (всего)", "expenses_total"),
        ("  Озон комиссия (за вычетом возвратов)", "commission"),
        ("  Озон фулфилмент:", "fulfil_total"),
        ("    - логистика", "fulfil_logistics"),
        ("    - обратная логистика", "fulfil_reverse"),
        ("    - последняя миля", "fulfil_lastmile"),
        ("    - обработка, сборка", "fulfil_processing"),
        ("  Озон маркетинг:", "market_total"),
        ("    - реклама (PayPerClick)", "ppc"),
        ("    - продвижение, промо", "promo"),
        ("    - звёзды (Stars)", "stars"),
        ("    - бренд-комиссия", "brand"),
        ("    - отзывы", "reviews"),
        ("  Услуги агентов (эквайринг и пр.)", "agents"),
        ("  Услуги FBO", "fbo"),
        ("  Другие услуги", "other"),
        ("  Прочие начисления и компенсации", "misc"),
        ("", None),
        ("  Себестоимость (доставлено − возвращено)", "cogs"),
        ("", None),
        ("ВАЛОВАЯ ПРИБЫЛЬ", "margin"),
        ("", None),
        ("Операционные расходы (всего)", None),
        ("  - расходы на персонал", None),
        ("  - административные расходы", None),
        ("  - коммерческие расходы", None),
        ("  - прочие операционные (взносы ИП, 1/12)", "contrib"),
        ("", None),
        ("ОПЕРАЦИОННАЯ ПРИБЫЛЬ (EBITDA)", "margin"),
        ("", None),
        ((f"Налог УСН Д−Р {tax_rate*100:.0f}% (мин. 1% от доходов)" if regime == REGIME_DR
          else f"Налог УСН доходы {tax_rate*100:.0f}% (минус взносы ИП)"), "tax"),
        ("", None),
        ("ЧИСТАЯ ПРИБЫЛЬ", "net"),
        ("Рентабельность к себестоимости (ROI)", "roi"),
        ("Выплата дивидендов", None),
        ("Нераспределённая прибыль", "net"),
        ("Накопленная прибыль", "net"),
    ]

    # Эти ключи — всегда расход, пишем со знаком минус. Категории услуг Ozon
    # уже со знаком из accruals_services (компенсации — плюсом), их не трогаем.
    NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission", "tax", "contrib"}

    base_year = sum(d.get("revenue", 0) for d in by_month.values())

    for label, key in lines:
        row = [""] * 20
        row[0] = label
        if key is None:
            rows.append(row)
            continue

        r_num = len(rows) + 1
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"
        skip_pct = label.strip().lower() in ("заказы (справочно)", "начислено баллов")
        if not skip_pct:
            row[COL_PCT - 1] = f"=IF($B$5=0;0;B{r_num}/$B$5*100)"

        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num) - 1] = round(val, 2)

        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(mcol(m1))
            cB = col_letter(mcol(m2))
            row[qcol(q) - 1] = f"=SUM({cA}{r_num}:{cB}{r_num})"

        year_val = sum(d.get(key, 0) for d in by_month.values())
        if key in NEGATIVE:
            year_val = -abs(year_val)
        pct_signed = (year_val / base_year * 100) if base_year else 0
        row[COL_VERDICT - 1] = make_verdict(label, pct_signed)

        rows.append(row)

    add_calc_formulas(rows)
    return rows


def apply_format(ws, n_rows):
    """Оставлено для совместимости. Не вызывается — стиль в pnl_format.py."""
    pass


def read_operational(ws):
    """Читает ручной ввод из колонок C:N (месяцы) строк 37-40."""
    saved = {}
    # Строка 40 (взносы ИП) теперь заполняется скриптом — не сохраняем.
    for r in (37, 38, 39):
        try:
            row = ws.row_values(r, value_render_option="UNFORMATTED_VALUE")
            for idx in range(3, 15):
                if idx < len(row):
                    v = row[idx]
                    if v is None or str(v).strip() in ("", "0"):
                        continue
                    try:
                        float(str(v).replace(" ", "").replace("\xa0", "").replace(",", "."))
                    except ValueError:
                        continue  # мусор вроде «%» не восстанавливаем
                    saved[f"{col_letter(idx+1)}{r}"] = v
        except Exception:
            pass
    return saved


def restore_operational(ws, saved):
    if not saved:
        print("[i] Ручных значений не найдено")
        return
    updates = []
    for addr, val in saved.items():
        try:
            num = float(str(val).replace(" ", "").replace("\xa0", "").replace(",", "."))
            updates.append({"range": addr, "values": [[num]]})
        except (ValueError, AttributeError):
            updates.append({"range": addr, "values": [[val]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"[OK] Восстановлено ручных значений: {len(saved)}")


# Строки P&L, которые заполняются из блока «РАСХОДЫ ПО МЕСЯЦАМ» листа НАСТРОЙКИ
MANUAL_ROWS = ((37, "staff"), (38, "admin"), (39, "commercial"), (48, "personal"))


def read_manual_expenses(sh):
    """Ручные расходы по месяцам с листа НАСТРОЙКИ (читает unitka/settings.py).
    Возвращает {месяц: {staff, admin, commercial, personal, …}} или None, если блока нет."""
    try:
        project = os.path.dirname(APP_DIR)
        if not sys.path or sys.path[0] != project:
            sys.path.insert(0, project)
        from unitka import settings as pult_settings
        return pult_settings.outflows(sh)
    except Exception as e:  # noqa: BLE001
        print(f"[i] Блок «РАСХОДЫ ПО МЕСЯЦАМ» не прочитан ({e}) — строки 37–39 остаются ручными")
        return None


def apply_manual_expenses(ws, block):
    """Пишет персонал / административные / коммерческие (строки 37–39) и личные выводы
    (строка 48 «Выплата дивидендов») со знаком минус. Пустые ячейки блока не трогают то,
    что введено в P&L вручную."""
    if not block:
        return
    updates = []
    for row, key in MANUAL_ROWS:
        for m in range(1, 13):
            val = (block.get(m) or {}).get(key) or 0.0
            if val:
                updates.append({"range": f"{col_letter(3 + m)}{row}", "values": [[-abs(val)]]})
    if not updates:
        print("[i] НАСТРОЙКИ → «Расходы по месяцам»: персонал/административные/коммерческие/личные не заполнены")
        return
    updates.append({"range": "B48", "values": [["=SUM(D48:O48)"]]})
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"[OK] Расходы из НАСТРОЕК перенесены в P&L: {len(updates) - 1} ячеек (строки 37–39, 48)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(args[0]) if args else 2026
    local = "--local" in sys.argv

    print("=" * 80)
    print(f"ВЫГРУЗКА P&L ЗА {year}  {'(локально)' if local else ''}")
    print("=" * 80)

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    tax = get_tax_settings(sh)

    rows = build_table(year, tax)
    print(f"\nСтрок: {len(rows)}")

    if local:
        import csv
        out = os.path.join(APP_DIR, f"pnl_{year}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerows(rows)
        print(f"\n[OK] Сохранено: {out}")
        return

    try:
        ws = sh.worksheet("P&L")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="P&L", rows=100, cols=25)

    saved_op = read_operational(ws)
    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
    restore_operational(ws, saved_op)
    apply_manual_expenses(ws, read_manual_expenses(sh))
    print(f"Записано строк: {len(rows)}")

    # Стилизация — в PNL/pnl_format.py
    print("[i] Стилизация — в PNL/pnl_format.py")

    print(f"\nГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()


