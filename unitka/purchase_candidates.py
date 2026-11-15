"""Forecast candidates are not approved purchase recommendations."""
import math


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def forecast_candidates(rows):
    """Keep SKU and offer separate; omit invalid or repeated SKU records.

    A forecast alone never authorizes procurement. No suggested buy quantity
    is returned, even when a forecast is positive.
    """
    prepared = []
    counts = {}
    for row in rows:
        raw_sku = row.get("sku")
        sku = str(raw_sku).strip() if raw_sku is not None else ""
        if isinstance(raw_sku, bool) or not sku.isascii() or not sku.isdigit() or int(sku) <= 0:
            continue
        sku = str(int(sku))
        counts[sku] = counts.get(sku, 0) + 1
        qty = _number(row.get("forecast_qty"))
        revenue = _number(row.get("forecast_revenue"))
        if qty is None or qty <= 0 or (revenue is not None and revenue < 0):
            continue
        offer = row.get("offer_id")
        prepared.append({"sku": sku, "offer_id": str(offer).strip() if offer is not None else "",
                         "forecast_qty": qty, "forecast_revenue": revenue,
                         "purchase_approved": False,
                         "reason": "Прогноз не является объёмом закупки. Требуется проверка остатков, спроса и полной экономики."})
    return sorted((r for r in prepared if counts[r["sku"]] == 1),
                  key=lambda r: (-r["forecast_qty"], int(r["sku"])))


def candidate_text(row):
    """Render informational demand only; never turn missing checks into approval."""
    label = row["offer_id"] or row["sku"]
    return (f"{label} (SKU {row['sku']}): прогноз спроса {row['forecast_qty']:g} шт. "
            "Закупка не согласована: сначала проверить остатки, спрос и полную экономику.")
