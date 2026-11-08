"""unitka/log_change.py — журнал изменений цен, остатков, рекламы."""
import logging
from datetime import datetime

from .db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def log_change(sku: str, field: str, old_value, new_value, source: str = "manual", comment: str = ""):
    """Записывает изменение в журнал.

    sku: артикул или SKU товара
    field: 'price', 'stock', 'ad', 'description', 'promo'
    old_value, new_value: значения до и после (могут быть None)
    source: 'manual' (менеджер), 'auto' (скрипт), 'ozon' (Ozon API)
    comment: произвольный комментарий
    """
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO change_log (date, sku, field, old_value, new_value, source, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(sku),
        field,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        source,
        comment,
    ))
    conn.commit()
    conn.close()
    logger.info("Изменение записано: SKU=%s, поле=%s, %s → %s", sku, field, old_value, new_value)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Использование: python -m unitka.log_change <sku> <field> <old> <new> [comment]")
        sys.exit(1)
    sku, field, old, new = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None
    comment = sys.argv[5] if len(sys.argv) > 5 else ""
    log_change(sku, field, old, new, source="manual", comment=comment)
