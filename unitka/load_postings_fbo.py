"""Загрузка FBO-отправлений через /v2/posting/fbo/list."""
import argparse, json, logging, sqlite3
from unitka import config
from unitka.ozon_client import OzonClient

logger = logging.getLogger(__name__)
LIMIT = 1000


def _client():
    config.check_credentials()
    return OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY,
                      base=config.OZON_BASE_URL)


def _iso(d, end=False):
    t = "23:59:59.999" if end else "00:00:00.000"
    return f"{d}T{t}Z"


def fetch_postings(client, date_from, date_to):
    all_postings, offset = [], 0
    since, to = _iso(date_from), _iso(date_to, True)
    logger.info(f"FBO запрос: since={since} to={to}")
    while True:
        payload = {
            "dir": "ASC",
            "filter": {"since": since, "to": to},
            "limit": LIMIT,
            "offset": offset,
            "with": {"analytics_data": True, "financial_data": True},
        }
        data = client._post("/v2/posting/fbo/list", payload)
        # /v2/posting/fbo/list возвращает result как список напрямую
        postings = data.get("result") or []
        all_postings.extend(postings)
        logger.info(f"offset={offset} получено {len(postings)}")
        # если меньше лимита — это конец
        if len(postings) < LIMIT:
            break
        offset += LIMIT
    return all_postings


def save_postings(postings, date_from, date_to):
    con = sqlite3.connect(str(config.DB_PATH))
    cur = con.cursor()
    cur.execute("DELETE FROM postings_daily WHERE date BETWEEN ? AND ? AND source='api_fbo'",
                (date_from, date_to))
    rows = []
    statuses = {}
    skipped_no_date = 0
    for p in postings:
        status = p.get("status") or ""
        statuses[status] = statuses.get(status, 0) + 1

        # для FBO берём created_at (дата создания), fallback — in_process_at
        order_date = (p.get("created_at") or p.get("in_process_at") or "")[:10]
        if not order_date:
            skipped_no_date += 1
            continue

        is_cancelled = 1 if status == "cancelled" else 0
        is_returned  = 1 if "return" in status.lower() else 0

        fin = p.get("financial_data") or {}
        commission_total = 0
        for fp in (fin.get("products") or []):
            commission_total += float(fp.get("commission_amount") or 0)

        posting_number = p.get("posting_number")
        for prod in (p.get("products") or []):
            rows.append((
                order_date, posting_number,
                str(prod.get("sku") or ""),
                int(prod.get("quantity") or 1),
                float(prod.get("price") or 0),
                float(commission_total),
                is_cancelled, is_returned, status, "api_fbo",
                json.dumps(p, ensure_ascii=False),
            ))

    cur.executemany("""
        INSERT INTO postings_daily
            (date, posting_number, sku, quantity, price, commission,
             is_cancelled, is_returned, status, source, raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()
    logger.info(f"Сохранено {len(rows)} строк (source=api_fbo), "
                f"пропущено без даты: {skipped_no_date}")
    logger.info("Статусы FBO:")
    for s, n in sorted(statuses.items(), key=lambda x: -x[1]):
        logger.info(f"  {s!r}: {n}")
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--to",   dest="date_to",   required=True)
    args = ap.parse_args()
    client = _client()
    postings = fetch_postings(client, args.date_from, args.date_to)
    logger.info(f"Всего получено {len(postings)} FBO отправлений")
    save_postings(postings, args.date_from, args.date_to)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()