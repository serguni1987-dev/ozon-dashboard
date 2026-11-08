"""unitka/run_analytics.py — оркестратор аналитического пайплайна."""
import argparse
import logging
import sys
import time
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def step_with_retry(name, func, *args, **kwargs):
    """Запускает шаг. Если ошибка 429 (Quota), ждет 65 секунд и пробует снова (до 2 раз)."""
    attempts = 3
    for attempt in range(1, attempts + 1):
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"ШАГ: {name} (попытка {attempt}/{attempts})")
        logger.info("=" * 60)
        try:
            func(*args, **kwargs)
            logger.info(f"[OK] {name}")
            return True
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Quota exceeded" in err_str:
                if attempt < attempts:
                    logger.warning(f"Google Quota Exceeded (429). Ждем 65 секунд и пробуем снова...")
                    time.sleep(65)
                else:
                    logger.error(f"[FAIL] {name}: квота Google так и не восстановилась после {attempts} попыток.")
                    return False
            else:
                logger.error(f"[FAIL] {name}: {type(e).__name__}: {e}")
                return False
    return False

def main():
    parser = argparse.ArgumentParser(description='Аналитический пайплайн Ozon')
    parser.add_argument('--from', dest='date_from', default=(date.today() - timedelta(days=270)).isoformat())
    parser.add_argument('--to', dest='date_to', default=(date.today() - timedelta(days=1)).isoformat())
    parser.add_argument('--skip-sku-map', action='store_true', help='Пропустить пересборку карты SKU')
    args = parser.parse_args()

    logger.info(f"АНАЛИТИЧЕСКИЙ ПАЙПЛАЙН: {args.date_from} — {args.date_to}")

    from . import build_sku_map, calc_abc_xyz, calc_pulse, calc_unit_summary, load_sales_xlsx, calc_funnel

    results = []

    # 0. Воронка: загрузка свежего .xlsx из app/downloads (не падает, если папка пустая)
    try:
        load_sales_xlsx.main()
    except SystemExit:
        pass
    except Exception as e:
        logger.warning(f"[WARN] Загрузка xlsx: {type(e).__name__}: {e}")

    if not args.skip_sku_map:
        results.append(('1. Сборка карты SKU', step_with_retry('build_sku_map', build_sku_map.main)))
        time.sleep(10)
    else:
        logger.info("[SKIP] Сборка карты SKU пропущена")

    results.append(('2. ABC/XYZ-анализ', step_with_retry('calc_abc_xyz', calc_abc_xyz.main, ['--from', args.date_from, '--to', args.date_to])))

    time.sleep(10)
    results.append(('3. Юнит-сводка', step_with_retry('calc_unit_summary', calc_unit_summary.main)))

    time.sleep(10)
    results.append(('4. Лист Воронка', step_with_retry('calc_funnel', calc_funnel.main)))

    time.sleep(10)
    results.append(('5. Лист ПУЛЬТ', step_with_retry('calc_pulse', calc_pulse.main)))

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