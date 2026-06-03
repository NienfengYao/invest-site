# app/services/cost_engine.py

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.monthly_price import MonthlyPrice
from app.models.monthly_holding import MonthlyHolding
from app.core.ticker import normalize_ticker
from app.services.account_summary import resolve_ticker


@dataclass
class HoldingState:
    shares: float = 0.0
    total_cost: float = 0.0

    @property
    def avg_cost(self) -> float:
        if self.shares == 0:
            return 0.0
        return self.total_cost / self.shares


def _get_trade_date(tx: Transaction) -> datetime:
    """
    Convert transaction trade_date to datetime.
    Supports:
        - datetime
        - date
        - string
    """

    if isinstance(tx.trade_date, datetime):
        return tx.trade_date

    if isinstance(tx.trade_date, str):

        for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(tx.trade_date, fmt)
            except ValueError:
                pass

        raise ValueError(f"Unsupported trade_date format: {tx.trade_date}")

    return datetime.combine(tx.trade_date, datetime.min.time())


def _year_month(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _get_monthly_price_map(db: Session) -> Dict[Tuple[str, str], float]:
    rows = db.query(MonthlyPrice).all()

    price_map = {}
    for row in rows:
        ticker = normalize_ticker(row.ticker)
        price_map[(ticker, row.year_month)] = float(row.close_price)

    return price_map


def _delete_existing_snapshots(account_id: int, db: Session) -> int:
    deleted = (
        db.query(MonthlyHolding)
        .filter(MonthlyHolding.account_id == account_id)
        .delete()
    )
    db.flush()
    return deleted


def _apply_buy(state: HoldingState, quantity: float, net_amount: float) -> None:
    state.shares += quantity
    # BUY cost should always be positive
    state.total_cost += abs(net_amount)


def _apply_sell(state: HoldingState, quantity: float, net_amount: float) -> float:
    if state.shares <= 0:
        return 0.0

    sell_qty = min(quantity, state.shares)

    sold_cost = state.avg_cost * sell_qty
    realized_gain = net_amount - sold_cost

    state.shares -= sell_qty
    state.total_cost -= sold_cost

    if abs(state.shares) < 0.000001:
        state.shares = 0.0
        state.total_cost = 0.0

    return realized_gain


def _iter_months(start_ym: str, end_ym: str):
    start_year, start_month = map(int, start_ym.split("-"))
    end_year, end_month = map(int, end_ym.split("-"))

    year = start_year
    month = start_month

    while (year < end_year) or (year == end_year and month <= end_month):
        yield f"{year:04d}-{month:02d}"

        month += 1
        if month == 13:
            month = 1
            year += 1


def rebuild_monthly_holdings(account_id: int, db: Session) -> dict:
    """
    Rebuild monthly holding snapshots for one account.

    Input:
        transactions

    Output:
        monthly_holdings

    Accounting method:
        Average Cost
    """

    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .order_by(Transaction.trade_date.asc(), Transaction.id.asc())
        .all()
    )

    if not transactions:
        return {
            "account_id": account_id,
            "transactions": 0,
            "snapshots_created": 0,
            "message": "No transactions found.",
        }

    _delete_existing_snapshots(account_id, db)

    price_map = _get_monthly_price_map(db)


    holdings: Dict[str, HoldingState] = defaultdict(HoldingState)
    monthly_snapshots = {}
    realized_gain_by_month = defaultdict(float)

    # 依月份分組交易
    tx_by_month = defaultdict(list)
    for tx in transactions:
        trade_date = _get_trade_date(tx)
        ym = _year_month(trade_date)
        tx_by_month[ym].append(tx)

    first_month = min(tx_by_month.keys())

    # 最後月份：用 monthly_prices 的最後月份
    price_months = [ym for (_ticker, ym) in price_map.keys()]
    if price_months:
        last_month = max(price_months)
    else:
        last_month = max(tx_by_month.keys())

    # 逐月建立 snapshot，沒有交易的月份也 carry-forward
    for ym in _iter_months(first_month, last_month):
        month_txs = tx_by_month.get(ym, [])

        for tx in month_txs:
            ticker = normalize_ticker(resolve_ticker(tx.stock_name))
            quantity = float(tx.quantity or 0)
            net_amount = float(tx.net_amount or 0)
            tx_type = (tx.side or "").upper()

            state = holdings[ticker]

            if tx_type == "BUY":
                _apply_buy(state, quantity, net_amount)

            elif tx_type == "SELL":
                realized_gain = _apply_sell(state, quantity, net_amount)
                realized_gain_by_month[ym] += realized_gain

            else:
                continue

        # 每個月月底都記錄一次持股狀態
        for holding_ticker, holding_state in holdings.items():
            if holding_state.shares <= 0:
                continue

            monthly_snapshots[(ym, holding_ticker)] = HoldingState(
                shares=holding_state.shares,
                total_cost=holding_state.total_cost,
            )

    created = 0

    for (ym, ticker), state in sorted(monthly_snapshots.items()):
        if state.shares <= 0:
            continue

        market_price = price_map.get((ticker, ym))
        market_value = None
        unrealized_gain = None

        if market_price is not None:
            market_value = state.shares * market_price
            unrealized_gain = market_value - state.total_cost

        row = MonthlyHolding(
            account_id=account_id,
            year_month=ym,
            ticker=ticker,
            shares=state.shares,
            avg_cost=state.avg_cost,
            total_cost=state.total_cost,
            market_price=market_price,
            market_value=market_value,
            unrealized_gain=unrealized_gain,
        )

        db.add(row)
        created += 1

    db.commit()


    return {
        "account_id": account_id,
        "transactions": len(transactions),
        "snapshots_created": created,
        "realized_gain_months": dict(realized_gain_by_month),
    }
