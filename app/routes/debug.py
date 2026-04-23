from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.monthly_price import MonthlyPrice

from app.services.account_summary import resolve_ticker

from fastapi.templating import Jinja2Templates
from fastapi import Request

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/debug/db", response_class=HTMLResponse)
def debug_db(request: Request, db: Session = Depends(get_db)):

    # --- DB counts ---
    account_count = db.query(Account).count()
    transaction_count = db.query(Transaction).count()
    monthly_price_count = db.query(MonthlyPrice).count()

    # --- recent transactions ---
    recent_transactions = (
        db.query(Transaction)
        .order_by(Transaction.id.desc())
        .limit(10)
        .all()
    )

    # --- recent monthly prices ---
    recent_prices = (
        db.query(MonthlyPrice)
        .order_by(MonthlyPrice.year_month.desc())
        .limit(20)
        .all()
    )

    # --- unmapped stock names ---
    stock_names = db.query(Transaction.stock_name).distinct().all()

    unmapped = []
    for (name,) in stock_names:
        if resolve_ticker(name) is None:
            unmapped.append(name)

    return templates.TemplateResponse(
        "debug_db.html",
        {
            "request": request,
            "account_count": account_count,
            "transaction_count": transaction_count,
            "monthly_price_count": monthly_price_count,
            "recent_transactions": recent_transactions,
            "recent_prices": recent_prices,
            "unmapped": unmapped,
        },
    )


@router.get("/debug/health", response_class=HTMLResponse)
def debug_health(request: Request, db: Session = Depends(get_db)):

    checks = []

    # --- 1. DB 基本資料 ---
    account_count = db.query(Account).count()
    transaction_count = db.query(Transaction).count()
    monthly_price_count = db.query(MonthlyPrice).count()

    if transaction_count == 0:
        checks.append(("transactions", "ERROR", "沒有任何交易資料"))
    else:
        checks.append(("transactions", "OK", f"{transaction_count} 筆"))

    if monthly_price_count == 0:
        checks.append(("monthly_prices", "ERROR", "沒有月價資料"))
    else:
        checks.append(("monthly_prices", "OK", f"{monthly_price_count} 筆"))

    # --- 2. unmapped 股票 ---
    stock_names = db.query(Transaction.stock_name).distinct().all()
    unmapped = [name for (name,) in stock_names if resolve_ticker(name) is None]

    if unmapped:
        checks.append(("mapping", "WARN", f"{len(unmapped)} 個未對應"))
    else:
        checks.append(("mapping", "OK", "全部正常"))

    # --- 3. ticker 是否有月價 ---
    tickers = set(resolve_ticker(name) for (name,) in stock_names if resolve_ticker(name))
    price_tickers = set(p.ticker for p in db.query(MonthlyPrice.ticker).distinct())

    missing_price_tickers = tickers - price_tickers

    if missing_price_tickers:
        checks.append(("price_coverage", "WARN", f"{len(missing_price_tickers)} 檔沒有月價"))
    else:
        checks.append(("price_coverage", "OK", "全部有月價"))

    # --- 4. 檢查是否有持股但該月沒價格 ---
    missing_price_cases = []

    transactions = db.query(Transaction).all()
    monthly_prices = db.query(MonthlyPrice).all()

    price_map = {(p.ticker, p.year_month) for p in monthly_prices}

    for tx in transactions:
        ticker = resolve_ticker(tx.stock_name)
        if not ticker:
            continue

        try:
            month = tx.trade_date[:7].replace("/", "-")
        except:
            continue

        if (ticker, month) not in price_map:
            missing_price_cases.append((ticker, month))

    if missing_price_cases:
        checks.append(("month_price_missing", "WARN", f"{len(missing_price_cases)} 筆缺月價"))
    else:
        checks.append(("month_price_missing", "OK", "完整"))

    return templates.TemplateResponse(
        "debug_health.html",
        {
            "request": request,
            "checks": checks,
            "unmapped": unmapped,
            "missing_price_tickers": list(missing_price_tickers),
            "missing_price_cases": missing_price_cases[:20],  # 限制顯示
        },
    )
