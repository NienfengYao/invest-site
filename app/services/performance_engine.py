# app/services/performance_engine.py

from collections import defaultdict
from sqlalchemy.orm import Session
from datetime import datetime, date

from app.models.transaction import Transaction
from app.models.monthly_holding import MonthlyHolding
from app.models.monthly_performance import MonthlyPerformance
from app.models.dividend import Dividend
from app.services.account_summary import resolve_ticker
from app.core.ticker import normalize_ticker


def _year_month(date_str: str) -> str:
    """
    Convert:
        2025/01/15
    to:
        2025-01
    """

    return date_str[:7].replace("/", "-")


def _parse_trade_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass

    raise ValueError(f"Unsupported trade_date format: {value}")


def _tx_ticker(tx: Transaction) -> str | None:
    ticker = resolve_ticker(tx.stock_name)

    if not ticker:
        return None

    return normalize_ticker(ticker)


def _get_shares_on_date(
    account_id: int,
    ticker: str,
    target_date,
    transactions: list[Transaction],
) -> float:
    shares = 0.0

    for tx in transactions:
        if tx.account_id != account_id:
            continue

        tx_date = _parse_trade_date(tx.trade_date)

        if tx_date > target_date:
            continue

        tx_ticker = _tx_ticker(tx)

        if tx_ticker != ticker:
            continue

        side = (tx.side or "").upper()
        quantity = float(tx.quantity or 0)

        if side == "BUY":
            shares += quantity
        elif side == "SELL":
            shares -= quantity

    return max(shares, 0.0)


def _delete_existing(account_id: int, db: Session):
    (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == account_id)
        .delete()
    )

    db.flush()


def rebuild_monthly_performance(account_id: int, db: Session):

    _delete_existing(account_id, db)

    # =========================
    # Step 1: aggregate transactions
    # =========================

    tx_rows = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .all()
    )

    monthly_buy = defaultdict(float)
    monthly_sell = defaultdict(float)

    for tx in tx_rows:

        ym = _year_month(tx.trade_date)

        side = (tx.side or "").upper()

        amount = abs(float(tx.net_amount or 0))

        if side == "BUY":
            monthly_buy[ym] += amount

        elif side == "SELL":
            monthly_sell[ym] += amount

    # =========================
    # Step 2: aggregate holdings
    # =========================

    holding_rows = (
        db.query(MonthlyHolding)
        .filter(MonthlyHolding.account_id == account_id)
        .all()
    )

    monthly_total_cost = defaultdict(float)
    monthly_market_value = defaultdict(float)
    monthly_unrealized_gain = defaultdict(float)

    for row in holding_rows:

        ym = row.year_month

        monthly_total_cost[ym] += float(row.total_cost or 0)

        monthly_market_value[ym] += float(row.market_value or 0)

        monthly_unrealized_gain[ym] += float(row.unrealized_gain or 0)

    # =========================
    # Step 3: aggregate dividends
    # =========================

    dividend_rows = db.query(Dividend).all()

    monthly_dividend = defaultdict(float)

    for d in dividend_rows:
        ex_date = d.ex_dividend_date
        ym = ex_date.strftime("%Y-%m")
        ticker = normalize_ticker(d.ticker)

        shares = _get_shares_on_date(
            account_id=account_id,
            ticker=ticker,
            target_date=ex_date,
            transactions=tx_rows,
        )

        if shares <= 0:
            continue

        monthly_dividend[ym] += shares * float(d.dividend_per_share or 0)

    # =========================
    # Step 3: build performance rows
    # =========================

    all_months = set()

    all_months.update(monthly_buy.keys())
    all_months.update(monthly_sell.keys())
    all_months.update(monthly_total_cost.keys())
    all_months.update(monthly_dividend.keys())

    created = 0

    for ym in sorted(all_months):

        buy_amount = monthly_buy.get(ym, 0)
        sell_amount = monthly_sell.get(ym, 0)

        total_cost = monthly_total_cost.get(ym, 0)

        market_value = monthly_market_value.get(ym, 0)

        unrealized_gain = monthly_unrealized_gain.get(ym, 0)

        # v1: no dividend yet
        dividend_amount = monthly_dividend.get(ym, 0)

        # v1: no realized gain yet
        realized_gain = 0

        total_return = (
            unrealized_gain
            + realized_gain
            + dividend_amount
        )

        return_rate = 0

        if total_cost > 0:
            return_rate = total_return / total_cost

        row = MonthlyPerformance(
            account_id=account_id,

            year_month=ym,

            buy_amount=buy_amount,
            sell_amount=sell_amount,

            dividend_amount=dividend_amount,

            realized_gain=realized_gain,
            unrealized_gain=unrealized_gain,

            total_cost=total_cost,
            market_value=market_value,

            total_return=total_return,
            return_rate=return_rate,
        )

        db.add(row)

        created += 1

    db.commit()

    return {
        "account_id": account_id,
        "months": len(all_months),
        "rows_created": created,
    }
