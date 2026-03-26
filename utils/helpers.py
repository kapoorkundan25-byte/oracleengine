"""
utils/helpers.py — Small, reusable utility functions for OracleEngine.
"""

from __future__ import annotations

import datetime
from typing import Generator, TypeVar

T = TypeVar("T")


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a float as a percentage string.

    Args:
        value: Numeric value (e.g. ``0.4531`` → ``"45.31 %"``).
        decimals: Number of decimal places.

    Returns:
        Formatted percentage string such as ``"45.31 %"``.

    Examples:
        >>> format_percentage(0.4531)
        '45.31 %'
        >>> format_percentage(1.0)
        '100.00 %'
    """
    return f"{value * 100:.{decimals}f} %"


def format_currency(value: float, decimals: int = 2) -> str:
    """Format a float as a USD currency string.

    Args:
        value: Numeric value in US dollars.
        decimals: Number of decimal places.

    Returns:
        Formatted string such as ``"$1,234.56"``.

    Examples:
        >>> format_currency(1234.5678)
        '$1,234.57'
    """
    return f"${value:,.{decimals}f}"


def unix_to_datetime(ts: int | float) -> datetime.datetime:
    """Convert a Unix timestamp (seconds since epoch) to a UTC datetime.

    Args:
        ts: Unix timestamp as an integer or float.

    Returns:
        Timezone-aware :class:`datetime.datetime` in UTC.

    Examples:
        >>> unix_to_datetime(0)
        datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    """
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)


def chunk_list(lst: list[T], size: int) -> Generator[list[T], None, None]:
    """Split *lst* into successive chunks of at most *size* elements.

    Args:
        lst: The list to split.
        size: Maximum number of elements per chunk.

    Yields:
        Sub-lists of length ≤ *size*.

    Examples:
        >>> list(chunk_list([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError("chunk size must be a positive integer")
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
