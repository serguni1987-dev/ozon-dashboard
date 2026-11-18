"""Загрузка FBS-отправлений через /v4/posting/fbs/list."""
import argparse, json, logging, sqlite3
from unitka import config
from unitka.ozon_client import OzonClient

logger = logging.getLogger(__name__)
LIMIT = 100
def _f(v):
    """Безопасно достает число из числа, строки или словаря Ozon."""
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, dict):
        for k in ("amount", "price", "value"):
            if k in v: return _f(v[k])
        return 0.0
    s = str(v).replace(",", ".").strip()
    try: return float(s)
    except ValueError: return 0.0

def _client():
    config.check_credentials()
    return OzonClient()

def _iso(d, end=False):
    t = "23:59:59.999" if end else "00:00:00.000"
    return f"{d}T{t}Z"

def fetch_postings(client,date_from,date_to):
    from .postings_ingestion import fetch
    return fetch(client,date_from,date_to,scheme='fbs',limit=LIMIT)

def save_postings(postings,date_from,date_to):
    from pathlib import Path
    from contextlib import closing
    from .postings_ingestion import normalize,replace
    rows=normalize(postings,date_from,date_to,scheme='fbs');path=Path(config.DB_PATH).resolve()
    if not path.is_file():raise FileNotFoundError('Configured database does not exist')
    with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True)) as con:return replace(con,rows,date_from,date_to,scheme='fbs')

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
