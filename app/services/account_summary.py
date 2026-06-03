from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from app.models.monthly_price import MonthlyPrice
from app.models.transaction import Transaction


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


def parse_trade_date(date_str: str) -> datetime:
    formats = [
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    raise ValueError(f"Unsupported trade_date format: {date_str}")


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


def calculate_account_summary(transactions: list[Transaction]) -> dict[str, Any]:
    if not transactions:
        return {
            "total_buy_cost": 0.0,
            "total_sell_amount": 0.0,
            "first_trade_date": "",
            "last_trade_date": "",
        }

    buy_cost = sum(
        (t.cost or 0.0) + (t.fee or 0.0) + (t.tax or 0.0)
        for t in transactions
        if t.side == "BUY"
    )
    sell_amount = sum(
        (t.net_amount or 0.0)
        for t in transactions
        if t.side == "SELL"
    )

    dates = [t.trade_date for t in transactions if t.trade_date]

    return {
        "total_buy_cost": round(buy_cost, 2),
        "total_sell_amount": round(sell_amount, 2),
        "first_trade_date": min(dates) if dates else "",
        "last_trade_date": max(dates) if dates else "",
    }


def calculate_positions(transactions: list[Transaction]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Transaction]] = defaultdict(list)

    for tx in transactions:
        grouped[tx.stock_name].append(tx)

    positions: list[dict[str, Any]] = []

    for stock_name, items in grouped.items():
        buy_items = [t for t in items if t.side == "BUY"]
        sell_items = [t for t in items if t.side == "SELL"]

        total_buy_qty = sum(t.quantity or 0.0 for t in buy_items)
        total_sell_qty = sum(t.quantity or 0.0 for t in sell_items)
        current_qty = total_buy_qty - total_sell_qty

        if buy_items:
            buy_prices = [t.price or 0.0 for t in buy_items]
            total_buy_amount = sum((t.price or 0.0) * (t.quantity or 0.0) for t in buy_items)
            avg_price = (total_buy_amount / total_buy_qty) if total_buy_qty > 0 else 0.0
            min_price = min(buy_prices)
            max_price = max(buy_prices)
            total_buy_cost = sum((t.cost or 0.0) + (t.fee or 0.0) + (t.tax or 0.0) for t in buy_items)
        else:
            avg_price = 0.0
            min_price = 0.0
            max_price = 0.0
            total_buy_cost = 0.0

        total_sell_amount = sum(t.net_amount or 0.0 for t in sell_items)

        dates = [t.trade_date for t in items if t.trade_date]
        start_date = min(dates) if dates else ""
        end_date = max(dates) if dates else ""

        positions.append({
            "stock_name": stock_name,
            "current_qty": current_qty,
            "avg_price": round(avg_price, 4),
            "min_price": round(min_price, 4),
            "max_price": round(max_price, 4),
            "buy_cost": round(total_buy_cost, 2),
            "sell_amount": round(total_sell_amount, 2),
            "start_date": start_date,
            "end_date": end_date,
        })

    positions.sort(key=lambda x: x["stock_name"])
    return positions


def month_str_from_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


