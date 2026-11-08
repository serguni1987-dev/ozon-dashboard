"""Загрузка FBS-отправлений через /v3/posting/fbs/list.

filter.since / filter.to — по дате начала обработки (in_process_at).
Возвраты определяются по cancellation.cancelled_after_ship.
Сохраняет в postings_daily с source='api'.
"""
import argparse, json, logging, sqlite3
from unitka import config
from unitka.ozon_client import OzonClient

logger = logging.getLogger(__name__)
LIMIT = 50


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
    logger.info(f"Запрос: since={since} to={to}")
    while True:
        payload = {
            "dir": "ASC",
            "filter": {"since": since, "to": to},
            "limit": LIMIT,
            "offset": offset,
            "with": {"analytics_data": True, "financial_data": True},
        }
        data = client._post("/v3/posting/fbs/list", payload)
        result = data.get("result") or {}
        postings = result.get("postings") or []
        all_postings.extend(postings)
        logger.info(f"offset={offset} получено {len(postings)}")
        if not result.get("has_next") or not postings:
            break
        offset += LIMIT
    return all_postings


def save_postings(postings, date_from, date_to):
    con = sqlite3.connect(str(config.DB_PATH))
    cur = con.cursor()
    # Полная замена за период (удаляем и xlsx_report, и старый api)
    cur.execute("DELETE FROM postings_daily WHERE date BETWEEN ? AND ?",
                (date_from, date_to))
    rows = []
    statuses = {}
    skipped_no_date = 0
    for p in postings:
        status = p.get("status") or ""
        statuses[status] = statuses.get(status, 0) + 1

        # in_process_at — «Принят в обработку» (та же дата, что в XLSX-отчёте)
        order_date = (p.get("in_process_at") or "")[:10]
        if not order_date:
            skipped_no_date += 1
            continue

        # cancelled_after_ship — это тоже ОТМЕНА (клиент отказался на ПВЗ/в пути).
        # Возврат — только status возврата, отдельный от cancelled.
        is_cancelled = 1 if status == "cancelled" else 0
        is_returned  = 1 if "return" in status.lower() else 0

        fin = p.get("financial_data") or {}
        commission_total = fin.get("commission_amount") or 0
        posting_number = p.get("posting_number")

        for prod in (p.get("products") or []):
            rows.append((
                order_date, posting_number,
                str(prod.get("sku") or ""),
                int(prod.get("quantity") or 1),
                float(prod.get("price") or 0),
                float(commission_total),
                is_cancelled, is_returned, status, "api",
                json.dumps(p, ensure_ascii=False),
            ))

    cur.executemany("""
        INSERT INTO postings_daily
            (date, posting_number, sku, quantity, price, commission,
             is_cancelled, is_returned, status, source, raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()
    logger.info(f"Сохранено {len(rows)} строк (source=api), "
                f"пропущено без даты: {skipped_no_date}")
    logger.info("Статусы (по отправлениям):")
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
    logger.info(f"Всего получено {len(postings)} отправлений")
    save_postings(postings, args.date_from, args.date_to)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()