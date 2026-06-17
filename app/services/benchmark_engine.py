from typing import Any
from sqlalchemy.orm import Session
from app.models.monthly_holding import MonthlyHolding


def calculate_account_benchmark(account_id: int, db: Session) -> dict[str, Any]:
    latest_row = (
        db.query(MonthlyHolding)
        .filter(MonthlyHolding.account_id == account_id)
        .order_by(MonthlyHolding.year_month.desc())
        .first()
    )

    if not latest_row:
        return {
            "year_month": None,
            "rows": [],
            "total": None,
        }

    latest_month = latest_row.year_month

    holdings = (
        db.query(MonthlyHolding)
        .filter(
            MonthlyHolding.account_id == account_id,
            MonthlyHolding.year_month == latest_month,
        )
        .order_by(MonthlyHolding.market_value.desc())
        .all()
    )

    rows = []

    total_cost = 0.0
    total_market_value = 0.0
    total_unrealized_gain = 0.0

    for h in holdings:
        cost = float(h.total_cost or 0)
        market_value = float(h.market_value or 0)
        unrealized_gain = float(h.unrealized_gain or 0)

        return_rate = 0.0
        if cost > 0:
            return_rate = unrealized_gain / cost

        rows.append({
            "ticker": h.ticker,
            "shares": h.shares,
            "avg_cost": h.avg_cost,
            "market_price": h.market_price,
            "total_cost": cost,
            "market_value": market_value,
            "unrealized_gain": unrealized_gain,
            "return_rate": return_rate,
        })

        total_cost += cost
        total_market_value += market_value
        total_unrealized_gain += unrealized_gain

    total_return_rate = 0.0
    if total_cost > 0:
        total_return_rate = total_unrealized_gain / total_cost

    return {
        "year_month": latest_month,
        "rows": rows,
        "total": {
            "total_cost": total_cost,
            "market_value": total_market_value,
            "unrealized_gain": total_unrealized_gain,
            "return_rate": total_return_rate,
        },
    }


def merge_positions_and_benchmark(positions, benchmark):
    benchmark_map = {
        row["ticker"]: row
        for row in benchmark.get("rows", [])
    }

    total_market_value = 0.0
    if benchmark.get("total"):
        total_market_value = float(benchmark["total"].get("market_value") or 0)

    rows = []

    for position in positions:
        ticker = position.get("ticker")
        b = benchmark_map.get(ticker, {})

        market_value = float(b.get("market_value") or 0)

        portfolio_pct = 0.0
        if total_market_value > 0:
            portfolio_pct = market_value / total_market_value

        rows.append({
            # from position
            "ticker": ticker,
            "name": position.get("name"),
            "shares": position.get("shares"),
            "avg_cost": position.get("avg_cost"),
            "low_price": position.get("low_price"),
            "high_price": position.get("high_price"),
            "buy_amount": position.get("buy_amount"),
            "sell_amount": position.get("sell_amount"),
            "start_date": position.get("start_date"),
            "end_date": position.get("end_date"),

            # from benchmark
            "market_price": b.get("market_price"),
            "total_cost": b.get("total_cost"),
            "market_value": b.get("market_value"),
            "unrealized_gain": b.get("unrealized_gain"),
            "return_rate": b.get("return_rate"),

            # calculated
            "portfolio_pct": portfolio_pct,
        })

    rows.sort(key=lambda x: float(x.get("market_value") or 0), reverse=True)

    return {
        "year_month": benchmark.get("year_month"),
        "rows": rows,
        "total": benchmark.get("total"),
    }
