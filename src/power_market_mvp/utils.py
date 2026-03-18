from __future__ import annotations

from typing import Any

from .models import RISK_LABELS


def risk_label(risk_preference: str) -> str:
    return RISK_LABELS.get(risk_preference, risk_preference)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def sanitize_hour_list(
    values: Any, allowed_hours: list[int], fallback: list[int]
) -> list[int]:
    normalized: list[int] = []
    allowed = set(allowed_hours)

    if isinstance(values, list):
        for raw_value in values:
            try:
                hour = int(raw_value)
            except (TypeError, ValueError):
                continue
            if hour in allowed and hour not in normalized:
                normalized.append(hour)

    return sorted(normalized) if normalized else fallback


def sanitize_text_list(values: Any, fallback: list[str], limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return fallback

    cleaned = [str(item).strip() for item in values if str(item).strip()]
    return cleaned[:limit] if cleaned else fallback


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_hours(hours: list[int]) -> str:
    return ", ".join(f"{hour:02d}:00" for hour in hours)
