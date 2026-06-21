# app/core/ticker.py

from typing import Optional


STOCK_NAME_TO_TICKER = {
    "富邦台50": "006208",
    "國泰永續高股息": "00878",
    "元大台灣50": "0050",
    "元大高股息": "0056",
    "群益台灣精選高息": "00919",
    "復華台灣科技優息": "00929",
    "國泰10Y+金融債": "00933B",
    "元大美債20年": "00679B",
    "元大美債20正2": "00680L",
    "主動群益台灣強棒": "00982A",
    "國泰台灣領袖50": "00922",
    "富邦特選高股息30": "00900",
}


def resolve_ticker(stock_name: str) -> Optional[str]:
    name = (stock_name or "").strip()
    if not name:
        return None

    upper_name = name.upper()

    if upper_name.isdigit():
        return upper_name

    if upper_name.endswith(".TW") or upper_name.endswith(".TWO"):
        return upper_name

    return STOCK_NAME_TO_TICKER.get(name)


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()

    if ticker.isdigit():
        return f"{ticker}.TW"

    return ticker


def resolve_normalized_ticker(stock_name: str) -> Optional[str]:
    ticker = resolve_ticker(stock_name)

    if not ticker:
        return None

    return normalize_ticker(ticker)


def display_ticker(ticker: str) -> str:
    if ticker.endswith(".TW"):
        return ticker[:-3]

    return ticker
