"""Pure report rules; no network, database, billing or AI side effects."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation


PROCESSING_LIMITS = {
    "images_per_batch": 20,
    "bytes_per_image": 10 * 1024 * 1024,
    "bytes_per_batch": 100 * 1024 * 1024,
    "pixels_per_image": 25_000_000,
    "max_image_side": 12_000,
    "rows_per_report": 5_000,
    "fields_per_dataset": 60,
    "datasets_per_report": 10,
    "views_per_report": 10,
    "blocks_per_view": 12,
    "custom_indicators_per_report": 20,
}


def planned_phase(start: date | None, end: date | None, *, today: date) -> str:
    """Caller supplies today's date in campaign timezone; never infers live status."""
    if start and end and start > end:
        raise ValueError("A data de início deve ser anterior ou igual à data final.")
    if start and today < start:
        return "before_planned_start"
    if end and today > end:
        return "after_planned_end"
    if start and end:
        return "within_planned_window"
    return "unknown"


def decimal_value(value):
    """Only normalized numeric strings/numbers. Unknown is distinct from zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Valor numérico inválido.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Valor numérico inválido.") from exc
    if not result.is_finite():
        raise ValueError("Valor numérico deve ser finito.")
    return result


def ratio(numerator, denominator, *, multiplier=1):
    a, b, scale = map(decimal_value, (numerator, denominator, multiplier))
    if a is None or b is None or b == 0 or scale is None:
        return None
    return a / b * scale


def goal_assessment(actual, target, *, direction: str, comparable: bool) -> str:
    """Comparable must be established by unit, definition, window and scope checks."""
    if direction not in ("minimum", "maximum"):
        raise ValueError("Direção de meta inválida.")
    if not comparable:
        return "not_comparable"
    value, goal = decimal_value(actual), decimal_value(target)
    if value is None or goal is None:
        return "unknown"
    if direction == "minimum":
        return "met" if value >= goal else "below_target"
    return "met" if value <= goal else "above_limit"


def metric_change(previous, current, *, comparable: bool,
                  percentage_points: bool = False) -> dict:
    """Compare validated snapshots; never add them or infer interval delivery.

    Caller validates definition, unit, scope and comparison basis first.
    Percentage inputs must be normalized to 0–100, not fractional ratios.
    Decimal results need string serialization at the API boundary.
    """
    result = {"status": "not_comparable", "difference": None,
              "relative_percent": None,
              "difference_unit": "percentage_points" if percentage_points else "metric_unit"}
    if not comparable:
        return result
    before, after = decimal_value(previous), decimal_value(current)
    if before is None or after is None:
        return dict(result, status="missing_value")
    difference = after - before
    result.update(status="unchanged" if difference == 0 else "changed",
                  difference=difference)
    # Relative growth from zero or a negative baseline is misleading here.
    if before > 0 and not percentage_points:
        result["relative_percent"] = difference / before * 100
    return result
