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
        func(*args, **kwargs)
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

    if not args.skip_fetch:
        results.append(('1. Загрузка транзакций', step('load_transactions', load_transactions.main, date_from, date_to)))
        results.append(('2. Загрузка остатков', step('load_stocks', load_stocks.load_stocks)))
    else:
        logger.info("[SKIP] Загрузка данных пропущена (--skip-fetch)")

    results.append(('3. Дебиторка / Выплаты', step('calc_receivables', calc_receivables.main, date_from, date_to, False)))
    results.append(('4. Баланс', step('calc_balance', calc_balance.main)))
    results.append(('5. Налоги', step('calc_taxes', calc_taxes.main)))
    results.append(('6. ДДС', step('calc_cashflow', calc_cashflow.main)))
    results.append(('7. Оборотный капитал / ROI', step('calc_working_capital', calc_working_capital.main)))
    results.append(('8. Деньги в товаре', step('calc_money_in_goods', calc_money_in_goods.main)))
    results.append(('9. Дашборд решений', step('calc_dashboard', calc_dashboard.main)))

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