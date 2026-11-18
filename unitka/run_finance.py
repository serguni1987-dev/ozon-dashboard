"""unitka/run_finance.py — оркестратор финансового пайплайна (все 9 шагов)."""
import argparse
import logging
import sys
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def step(name, func, *args, **kwargs):
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"ШАГ: {name}")
    logger.info("=" * 60)
    try:
        result = func(*args, **kwargs)
        if result is False or (
            isinstance(result, dict)
            and str(result.get('status', '')).strip().upper()
            in {'ERROR', 'FAIL', 'FAILED', 'PARTIAL', 'INCOMPLETE', 'SKIPPED'}
        ):
            logger.error(f"[FAIL] {name}: step reported an unsuccessful result")
            return False
        logger.info(f"[OK] {name}")
        return True
    except Exception as e:
        logger.error(f"[FAIL] {name}: {type(e).__name__}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Финансовый пайплайн: все 9 шагов')
    parser.add_argument('--from', dest='date_from', default=None)
    parser.add_argument('--to', dest='date_to', default=None)
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--skip-fetch', action='store_true')
    args = parser.parse_args()

    today = datetime.now()
    date_to = args.date_to or today.strftime('%Y-%m-%d')
    date_from = args.date_from or (today - timedelta(days=args.days)).strftime('%Y-%m-%d')

    logger.info(f"ФИНАНСОВЫЙ ПАЙПЛАЙН: {date_from} — {date_to}")

    from . import (
        load_transactions, calc_receivables, load_stocks,
        calc_balance, calc_taxes, calc_cashflow, calc_working_capital,
        calc_money_in_goods, calc_dashboard
    )

    results = []

    def required(label, name, func, *call_args, **call_kwargs):
        ok = step(name, func, *call_args, **call_kwargs)
        results.append((label, ok))
        if not ok:
            logger.error("Pipeline stopped; dependent stages were not started")
            raise SystemExit(1)

    if not args.skip_fetch:
        required('1. Загрузка транзакций', 'load_transactions', load_transactions.main, date_from, date_to)
        required('2. Загрузка остатков', 'load_stocks', load_stocks.load_stocks)
    else:
        logger.info("[SKIP] Загрузка данных пропущена (--skip-fetch)")

    required('3. Дебиторка / Выплаты', 'calc_receivables', calc_receivables.main, date_from, date_to, False)
    required('4. Баланс', 'calc_balance', calc_balance.main)
    required('5. Налоги', 'calc_taxes', calc_taxes.main)
    required('6. ДДС', 'calc_cashflow', calc_cashflow.main)
    required('7. Оборотный капитал / ROI', 'calc_working_capital', calc_working_capital.main)
    required('8. Деньги в товаре', 'calc_money_in_goods', calc_money_in_goods.main)
    required('9. Дашборд решений', 'calc_dashboard', calc_dashboard.main)

    logger.info("")
    logger.info("=" * 60)
    logger.info("ИТОГИ:")
    for name, ok in results:
        logger.info(f"  [{'OK' if ok else 'FAIL'}] {name}")
    logger.info("=" * 60)

    failed = sum(1 for _, ok in results if not ok)
    if failed:
        logger.warning(f"Провалено: {failed} из {len(results)} шагов")
        sys.exit(1)
    else:
        logger.info(f"Все {len(results)} шагов выполнены успешно!")

if __name__ == '__main__':
    main()
