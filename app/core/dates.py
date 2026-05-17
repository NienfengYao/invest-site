# app/core/dates.py

from datetime import datetime


def parse_trade_date(date_str: str) -> datetime:
    """
    Parse trade date from CSV.

    Supported:
        2025/01/15
        2025-01-15
    """

    formats = [
        "%Y/%m/%d",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass

    raise ValueError(f"Unsupported date format: {date_str}")


def year_month(dt: datetime) -> str:
    """
    Convert datetime to YYYY-MM.
    """

    return dt.strftime("%Y-%m")
