from __future__ import annotations

TRUE_LIKE_VALUES = {"1", "true", "yes", "y", "on"}


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in TRUE_LIKE_VALUES


def as_int(
    value: str | None,
    *,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    try:
        parsed = int(str(value or "").strip())
    except Exception:
        parsed = int(default)
    if min_value is not None:
        parsed = max(int(min_value), parsed)
    if max_value is not None:
        parsed = min(int(max_value), parsed)
    return parsed


def as_float(
    value: str | None,
    *,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    try:
        parsed = float(str(value or "").strip())
    except Exception:
        parsed = float(default)
    if min_value is not None:
        parsed = max(float(min_value), parsed)
    if max_value is not None:
        parsed = min(float(max_value), parsed)
    return parsed
