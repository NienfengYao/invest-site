from collections import defaultdict
from typing import Any

from app.models.transaction import Transaction


def calculate_account_summary(transactions: list[Transaction]) -> dict[str, Any]:
    if not transactions:
        return {
            "total_buy_cost": 0.0,
            "total_sell_amount": 0.0,
            "first_trade_date": "",
            "last_trade_date": "",
        }

    buy_cost = sum((t.cost or 0.0) + (t.fee or 0.0) + (t.tax or 0.0)
                   for t in transactions if t.side == "BUY")
    sell_amount = sum((t.net_amount or 0.0)
                      for t in transactions if t.side == "SELL")

    dates = [t.trade_date for t in transactions if t.trade_date]

    return {
        "total_buy_cost": buy_cost,
        "total_sell_amount": sell_amount,
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
