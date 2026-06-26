"""
Spaced repetition urgency calculator.

Formula: limit_days = 30 + (n / 50)^2 * 335
  n=0  → 30 days
  n=25 → ~114 days
  n=50 → 365 days

Returns urgency_ratio: 0.0 (fresh/green) to 1.0 (overdue/red).
Values > 1.0 are clamped to 1.0.
"""
from datetime import date


def get_urgency_ratio(attempt_count: int, last_attempt_date) -> float:
    if last_attempt_date is None:
        return 0.0

    n = min(attempt_count, 50)
    limit_days = 30 + (n / 50) ** 2 * 335

    if hasattr(last_attempt_date, 'date'):
        last_date = last_attempt_date.date()
    else:
        last_date = last_attempt_date

    days_elapsed = (date.today() - last_date).days
    ratio = days_elapsed / limit_days
    return min(round(ratio, 4), 1.0)


def urgency_color(ratio: float) -> str:
    """Return a hex color interpolated from green (#1D9E75) to red (#E24B4A)."""
    r = int(0x1D + (0xE2 - 0x1D) * ratio)
    g = int(0x9E + (0x4B - 0x9E) * ratio)
    b = int(0x75 + (0x4A - 0x75) * ratio)
    return f'#{r:02X}{g:02X}{b:02X}'
