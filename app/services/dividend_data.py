# app/services/dividend_data.py

import yfinance as yf

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.dividend import Dividend

from app.core.ticker import normalize_ticker
from app.services.account_summary import resolve_ticker


def _get_all_tickers(db: Session):

    rows = (
        db.query(Transaction.stock_name)
        .distinct()
        .all()
    )

    tickers = []

    for (stock_name,) in rows:

        ticker = resolve_ticker(stock_name)

        if not ticker:
            continue

        ticker = normalize_ticker(ticker)

        tickers.append(ticker)

    return sorted(list(set(tickers)))



def _delete_existing_dividends(
    ticker: str,
    db: Session,
):

    (
        db.query(Dividend)
        .filter(Dividend.ticker == ticker)
        .delete()
    )

    db.flush()


def fetch_and_store_dividends(
    db: Session,
):

    tickers = _get_all_tickers(db)

    result = {
        "total_tickers": len(tickers),
        "success": [],
        "failed": [],
        "inserted_rows": 0,
    }

    for ticker in tickers:

        try:

            yf_ticker = yf.Ticker(ticker)

            dividends = yf_ticker.dividends

            if dividends.empty:
                continue

            _delete_existing_dividends(
                ticker=ticker,
                db=db,
            )

            for ex_date, dividend_value in dividends.items():

                row = Dividend(
                    ticker=ticker,

                    ex_dividend_date=ex_date.date(),

                    pay_date=None,

                    dividend_per_share=float(dividend_value),
                )

                db.add(row)

                result["inserted_rows"] += 1

            result["success"].append(ticker)

        except Exception as e:

            result["failed"].append({
                "ticker": ticker,
                "error": str(e),
            })

    db.commit()

    return result
