# app/core/ticker.py

def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol.

    Examples:
        0050 -> 0050.TW
        2330 -> 2330.TW
        VOO -> VOO
    """

    ticker = ticker.strip().upper()

    if ticker.isdigit():
        return f"{ticker}.TW"

    return ticker


def display_ticker(ticker: str) -> str:
    """
    Convert internal ticker format to display format.

    Example:
        0050.TW -> 0050
    """

    if ticker.endswith(".TW"):
        return ticker[:-3]

    return ticker
