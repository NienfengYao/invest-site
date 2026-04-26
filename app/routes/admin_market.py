from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.monthly_price import MonthlyPrice

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/admin/market", response_class=HTMLResponse)
def admin_market(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(
            MonthlyPrice.ticker.label("ticker"),
            func.count(MonthlyPrice.id).label("row_count"),
            func.min(MonthlyPrice.year_month).label("first_month"),
            func.max(MonthlyPrice.year_month).label("last_month"),
        )
        .group_by(MonthlyPrice.ticker)
        .order_by(MonthlyPrice.ticker.asc())
        .all()
    )

    ticker_summaries = []

    for row in rows:
        latest_price = (
            db.query(MonthlyPrice)
            .filter(MonthlyPrice.ticker == row.ticker)
            .order_by(MonthlyPrice.year_month.desc())
            .first()
        )

        ticker_summaries.append({
            "ticker": row.ticker,
            "row_count": row.row_count,
            "first_month": row.first_month,
            "last_month": row.last_month,
            "latest_close": latest_price.close_price if latest_price else None,
            "latest_date": latest_price.month_end_date if latest_price else None,
        })

    total_rows = db.query(MonthlyPrice).count()
    total_tickers = len(ticker_summaries)
    latest_month = db.query(func.max(MonthlyPrice.year_month)).scalar()

    return templates.TemplateResponse(
        "admin_market.html",
        {
            "request": request,
            "total_rows": total_rows,
            "total_tickers": total_tickers,
            "latest_month": latest_month,
            "ticker_summaries": ticker_summaries,
        },
    )
