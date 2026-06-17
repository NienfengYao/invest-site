from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.dividend import Dividend
from app.models.monthly_price import MonthlyPrice
from app.models.monthly_holding import MonthlyHolding
from app.models.monthly_performance import MonthlyPerformance
from app.services.account_summary import resolve_ticker
from app.services.cost_engine import rebuild_monthly_holdings
from app.services.performance_engine import rebuild_monthly_performance
from app.services.dividend_data import fetch_and_store_dividends
from app.services.rebuild_from_uploads import rebuild_from_uploads
from app.services.system_debug import get_system_db_summary

from fastapi.templating import Jinja2Templates
from collections import defaultdict

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/debug/db", response_class=HTMLResponse)
def debug_db(
    request: Request,
    db: Session = Depends(get_db),
    account_id: Optional[int] = None,
    limit: str = "10",
    stocks: list[str] = Query(default=[]),
    sort_by: str = "trade_date",
    sort_order: str = "desc",
):
    accounts = db.query(Account).order_by(Account.id.asc()).all()

    if not accounts:
        return templates.TemplateResponse("debug_db.html", {
            "request": request,
            "error": "沒有帳戶資料"
        })

    # ⭐ 強制選擇帳戶
    selected_account_id = account_id or accounts[0].id
    selected_account = (
        db.query(Account)
        .filter(Account.id == selected_account_id)
        .first()
    )

    latest_performance = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == selected_account_id)
        .order_by(MonthlyPerformance.year_month.desc())
        .first()
    )

    # --- DB counts ---
    account_count = db.query(Account).count()
    transaction_count = db.query(Transaction).count()
    monthly_price_count = db.query(MonthlyPrice).count()
    transaction_count = db.query(Transaction).filter(
        Transaction.account_id == selected_account_id
    ).count()

    monthly_price_count = db.query(MonthlyPrice).count()

    # --- 股票清單 ---
    available_stocks = [
        name for (name,) in db.query(Transaction.stock_name)
        .filter(Transaction.account_id == selected_account_id)
        .distinct()
        .all()
    ]

    recent_prices = (
        db.query(MonthlyPrice)
        .order_by(MonthlyPrice.year_month.desc(), MonthlyPrice.ticker.asc())
        # .limit(20)
        .all()
    )

    recent_holdings = (
        db.query(MonthlyHolding)
        .filter(MonthlyHolding.account_id == selected_account_id)
        .order_by(
            MonthlyHolding.year_month.desc(),
            MonthlyHolding.ticker.asc()
        )
        # .limit(30)
        .all()
    )

    recent_performance = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == selected_account_id)
        .order_by(MonthlyPerformance.year_month.desc())
        # .limit(24)
        .all()
    )

    recent_dividends = (
        db.query(Dividend)
        .order_by(
            Dividend.ex_dividend_date.desc(),
            Dividend.ticker.asc()
        )
        # .limit(30)
        .all()
    )

    # --- 月價 ---
    monthly_prices = db.query(MonthlyPrice).all()
    price_map = {(p.ticker, p.year_month) for p in monthly_prices}

    # --- 偵測問題 ---
    unmapped = []
    missing_price_cases = []
    missing_price_details = defaultdict(list)

    for tx in db.query(Transaction).filter(
        Transaction.account_id == selected_account_id
    ):
        ticker = resolve_ticker(tx.stock_name)

        if not ticker:
            unmapped.append(tx.stock_name)
            continue

        month = tx.trade_date[:7].replace("/", "-")

        if (ticker, month) not in price_map:
            missing_price_cases.append((ticker, month))
            missing_price_details[ticker].append(month)

    # 去重
    unmapped = list(set(unmapped))
    missing_price_cases = list(set(missing_price_cases))
    missing_price_details = {
        ticker: sorted(set(months))
        for ticker, months in missing_price_details.items()
    }

    # --- health summary ---
    checks = []

    checks.append(("transactions", "OK" if transaction_count else "ERROR", str(transaction_count)))

    checks.append(("monthly_prices", "OK" if monthly_price_count else "ERROR", str(monthly_price_count)))

    checks.append(("mapping", "OK" if not unmapped else "WARN", f"{len(unmapped)} unmapped"))

    checks.append(("missing_price", "OK" if not missing_price_cases else "WARN", f"{len(missing_price_cases)} missing"))

    return templates.TemplateResponse(
        "debug_db.html",
        {
            "request": request,
            "account_count": account_count,
            "transaction_count": transaction_count,
            "monthly_price_count": monthly_price_count,
            "accounts": accounts,
            "selected_account_id": selected_account_id,
            "available_stocks": available_stocks,
            "selected_stocks": stocks,
            "selected_limit": limit,
            "selected_sort_by": sort_by,
            "selected_sort_order": sort_order,
            "recent_prices": recent_prices,
            "recent_holdings": recent_holdings,
            "recent_dividends": recent_dividends,
            "recent_performance": recent_performance,
            "checks": checks,
            "unmapped": unmapped,
            "missing_price_cases": missing_price_cases[:20],
            "missing_price_details": missing_price_details,
            "selected_account": selected_account,
            "latest_performance": latest_performance,
        },
    )

@router.get("/debug/rebuild-monthly-holdings/{account_id}")
def debug_rebuild_monthly_holdings(
    account_id: int,
    db: Session = Depends(get_db),
):
    return rebuild_monthly_holdings(account_id=account_id, db=db)

@router.get("/debug/rebuild-monthly-performance/{account_id}")
def debug_rebuild_monthly_performance(
    account_id: int,
    db: Session = Depends(get_db),
):
    return rebuild_monthly_performance(
        account_id=account_id,
        db=db,
    )

@router.get("/debug/update-dividends")
def debug_update_dividends(
    db: Session = Depends(get_db),
):
    return fetch_and_store_dividends(db=db)

@router.post("/admin/update-dividends", response_class=HTMLResponse)
def update_dividends_from_page(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = fetch_and_store_dividends(db=db)

        display_result = {
            "總股票數": result.get("total_tickers", 0),
            "成功股票": result.get("success", []),
            "新增股息筆數": result.get("inserted_rows", 0),
            "失敗股票": result.get("failed", []),
        }

        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "股息資訊更新完成",
                "success": True,
                "result": display_result,
                "message": "股息資訊已更新完成。",
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "股息資訊更新失敗",
                "success": False,
                "result": {},
                "message": str(exc),
            },
            status_code=500,
        )

@router.get("/debug/rebuild-from-uploads/{account_id}")
def debug_rebuild_from_uploads(
    account_id: int,
    db: Session = Depends(get_db),
):
    return rebuild_from_uploads(
        account_id=account_id,
        db=db,
    )

@router.get("/debug/system")
def system_debug(request: Request, db: Session = Depends(get_db)):
    tables = get_system_db_summary(db)

    return templates.TemplateResponse(
        "system_debug.html",
        {
            "request": request,
            "tables": tables,
        },
    )
