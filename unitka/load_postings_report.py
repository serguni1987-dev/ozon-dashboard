"""load_postings_report.py — выгрузка отчёта SELLER_POSTINGS из Ozon.

Ozon отдаёт отчёт в формате CSV (BOM + ; разделитель), не XLSX.
"""
import argparse, io, json, logging, re, sqlite3, time, urllib.request
from unitka import config
from unitka.ozon_client import OzonClient

logger = logging.getLogger(__name__)
NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _f(x):
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("\u00a0", "").replace(" ", "").replace("\u20bd", "")
    if not s:
        return 0.0
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        m = NUM_RE.search(s)
        return float(m.group(0).replace(",", ".")) if m else 0.0


def _parse_date(s):
    """'01.09.2026 12:34:56' или '2026-09-01T...' -> 'YYYY-MM-DD'."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s[:10]
    return None


def _client():
    config.check_credentials()
    return OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY,
                      base=config.OZON_BASE_URL)


def create_report(client, date_from, date_to):
    payload = {
        "filter": {
            "processed_at_from": f"{date_from}T00:00:00.000Z",
            "processed_at_to":   f"{date_to}T23:59:59.999Z",
            "delivery_schema":   ["fbs"],
            "sku": [], "cancel_reason_id": [], "offer_id": "",
            "status_alias": [], "statuses": [], "title": "",
        }
    }
    data = client._post("/v1/report/postings/create", payload)
    code = (data.get("result") or {}).get("code")
    if not code:
        raise RuntimeError(f"Нет code: {data}")
    logger.info(f"Отчёт создан, code={code}")
    return code


def wait_report(client, code, timeout=600, interval=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        data = client._post("/v1/report/info", {"code": code})
        res = data.get("result") or {}
        status = res.get("status")
        logger.info(f"status={status}")
        if status == "success":
            return res.get("file")
        if status in ("failed", "error"):
            raise RuntimeError(f"Отчёт упал: {res}")
        time.sleep(interval)
    raise TimeoutError(f"Отчёт не готов за {timeout}s")


def download(url):
    logger.info(f"Скачиваю: {url[:120]}")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (ozon-dashboard)")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        ct = r.headers.get("Content-Type")
    logger.info(f"Скачано {len(data)} байт, content-type={ct}")
    return data


def parse(content):
    """Универсальный парсер: CSV (BOM / ;) или XLSX (PK)."""
    if content[:2] == b"PK":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        out = [dict(zip(header, r)) for r in rows[1:] if any(r)]
        logger.info(f"Колонки (XLSX): {header}")
        return header, out

    import csv as _csv
    text = content.decode("utf-8-sig", errors="replace")
    first = text.split("\n", 1)[0]
    delim = ";" if first.count(";") >= first.count(",") else ","
    reader = _csv.reader(io.StringIO(text), delimiter=delim, quotechar='"')
    rows = list(reader)
    if not rows:
        return [], []
    header = [h.strip().lstrip("\ufeff") for h in rows[0]]
    logger.info(f"Колонки (CSV, delim={delim!r}): {header}")
    out = []
    for r in rows[1:]:
        if not any(r):
            continue
        out.append({header[i]: (r[i] if i < len(r) else None) for i in range(len(header))})
    return header, out


def save_rows(rows, date_from, date_to):
    con = sqlite3.connect(str(config.DB_PATH))
    cur = con.cursor()
    cur.execute("DELETE FROM postings_daily WHERE date BETWEEN ? AND ? AND source='xlsx_report'",
                (date_from, date_to))

    def g(row, *names):
        for n in names:
            v = row.get(n)
            if v not in (None, ""):
                return v
        return None

    out = []
    skipped_no_date = 0
    status_counter = {}
    for row in rows:
        d = (_parse_date(g(row, "Принят в обработку"))
             or _parse_date(g(row, "Дата отгрузки"))
             or _parse_date(g(row, "Дата доставки")))
        if not d:
            skipped_no_date += 1
            continue

        status = str(g(row, "Статус") or "").strip()
        status_counter[status] = status_counter.get(status, 0) + 1
        st = status.lower()

        date_cancel = _parse_date(g(row, "Дата отмены"))
        is_cancelled = 1 if (date_cancel or "отмен" in st or "cancel" in st) else 0
        is_returned = 1 if ("возврат" in st or "return" in st) else 0

        pn = str(g(row, "Номер отправления") or "").strip()
        sku = str(g(row, "SKU") or "").strip()
        qty = _f(g(row, "Количество")) or 1
        price = _f(g(row, "Сумма отправления") or g(row, "Оплачено покупателем")
                   or g(row, "Выкуп товара"))

        out.append((d, pn, sku, int(qty), price, 0.0,
                    is_cancelled, is_returned, status, "xlsx_report",
                    json.dumps(row, ensure_ascii=False, default=str)))

    cur.executemany("""
        INSERT INTO postings_daily
            (date, posting_number, sku, quantity, price, commission,
             is_cancelled, is_returned, status, source, raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, out)
    con.commit()
    logger.info(f"Сохранено {len(out)} строк, пропущено без даты: {skipped_no_date}")
    logger.info("Уникальные статусы в отчёте:")
    for s, n in sorted(status_counter.items(), key=lambda x: -x[1]):
        logger.info(f"  {s!r}: {n}")
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to",   dest="date_to",   required=True)
    ap.add_argument("--keep-xlsx", default=None, help="сохранить сырой файл (на самом деле CSV)")
    args = ap.parse_args()

    client = _client()
    code = create_report(client, args.date_from, args.date_to)
    url = wait_report(client, code)
    content = download(url)
    if args.keep_xlsx:
        with open(args.keep_xlsx, "wb") as f:
            f.write(content)
    _, rows = parse(content)
    logger.info(f"Разобрано {len(rows)} строк")
    save_rows(rows, args.date_from, args.date_to)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()