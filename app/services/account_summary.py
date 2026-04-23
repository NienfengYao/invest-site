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


def calculate_account_monthly_summary(
    transactions: list[Transaction],
    monthly_prices: list[MonthlyPrice],
) -> list[dict[str, Any]]:
    """
    先做帳戶月摘要：
    - month
    - monthly_invested
    - cumulative_invested
    - month_end_market_value
    - unrealized_gain

    說明：
    1. 以交易資料推導每月底持股數
    2. 用 monthly_prices 的月底價格算市值
    3. 當月投入：BUY 的 cost+fee+tax
    4. 累計投入：BUY 累加 - SELL net_amount 累加
       （先當作簡化版淨投入）
    """
    if not transactions or not monthly_prices:
        return []

    valid_transactions: list[tuple[datetime, Transaction]] = []
    for tx in transactions:
        try:
            valid_transactions.append((parse_trade_date(tx.trade_date), tx))
        except ValueError:
            print(f"[account_summary] invalid trade_date skipped: {tx.trade_date}")

    if not valid_transactions:
        return []

    valid_transactions.sort(key=lambda x: (x[0], x[1].id))

    # 價格表：month -> ticker -> close_price
    price_map: dict[str, dict[str, float]] = defaultdict(dict)
    months_set = set()

    for mp in monthly_prices:
        price_map[mp.year_month][mp.ticker] = mp.close_price
        months_set.add(mp.year_month)

    if not months_set:
        return []

    months = sorted(months_set)

    # 每月交易彙總
    monthly_buy_amount: dict[str, float] = defaultdict(float)
    monthly_sell_amount: dict[str, float] = defaultdict(float)

    # 截至每月底的持股數
    holdings: dict[str, float] = defaultdict(float)

    results: list[dict[str, Any]] = []
    tx_idx = 0
    tx_count = len(valid_transactions)

    cumulative_invested = 0.0

    for month in months:
        # 先把這個月的交易推進 holdings
        while tx_idx < tx_count and month_str_from_datetime(valid_transactions[tx_idx][0]) <= month:
            trade_dt, tx = valid_transactions[tx_idx]
            tx_month = month_str_from_datetime(trade_dt)

            ticker = resolve_ticker(tx.stock_name)
            if not ticker:
                print(f"[account_summary] unresolved stock_name: {tx.stock_name}")
                tx_idx += 1
                continue

            qty = tx.quantity or 0.0

            if tx.side == "BUY":
                holdings[ticker] += qty
                monthly_buy_amount[tx_month] += (tx.cost or 0.0) + (tx.fee or 0.0) + (tx.tax or 0.0)
            elif tx.side == "SELL":
                holdings[ticker] -= qty
                monthly_sell_amount[tx_month] += (tx.net_amount or 0.0)

            tx_idx += 1

        monthly_invested = monthly_buy_amount.get(month, 0.0) - monthly_sell_amount.get(month, 0.0)
        cumulative_invested += monthly_invested

        month_prices = price_map.get(month, {})
        market_value = 0.0

        for ticker, qty in holdings.items():
            if qty <= 0:
                continue

            close_price = month_prices.get(ticker)
            if close_price is None:
                continue

            market_value += qty * close_price

        unrealized_gain = market_value - cumulative_invested
        return_rate = (unrealized_gain / cumulative_invested * 100) if cumulative_invested > 0 else 0.0

        results.append({
            "month": month,
            "monthly_invested": round(monthly_invested, 2),
            "cumulative_invested": round(cumulative_invested, 2),
            "month_end_market_value": round(market_value, 2),
            "unrealized_gain": round(unrealized_gain, 2),
            "return_rate": round(return_rate, 2),
        })

    return results
