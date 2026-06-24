from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.monthly_price import MonthlyPrice
from app.models.maintenance_log import MaintenanceLog
from app.services.account_summary import (
    calculate_account_summary,
    calculate_positions,
)
from app.models.monthly_performance import MonthlyPerformance
from app.services.cost_engine import rebuild_monthly_holdings
from app.services.performance_engine import rebuild_monthly_performance
from app.services.benchmark_engine import (
    calculate_account_benchmark,
    merge_positions_and_benchmark,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("/site/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def clean_number(value) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip().replace(",", "")
    if text == "":
        return 0.0
    return float(text)


def read_broker_csv(contents: bytes) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "big5"]
    last_error = None

    for enc in encodings:
        try:
            df = pd.read_csv(BytesIO(contents), encoding=enc)
            break
        except Exception as exc:
            last_error = exc
    else:
        raise last_error  # type: ignore[misc]

    # 券商匯出有時第一列是說明文字，這裡自動修正
    required_columns = {"股名", "日期", "成交股數", "淨收付金額", "買賣別", "成交價", "成本", "手續費", "交易稅", "委託書號"}

    if not required_columns.issubset(set(df.columns)):
        df = pd.read_csv(BytesIO(contents), encoding="utf-8-sig", skiprows=1)
        if not required_columns.issubset(set(df.columns)):
            try:
                df = pd.read_csv(BytesIO(contents), encoding="big5", skiprows=1)
            except Exception:
                pass

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少欄位: {', '.join(sorted(missing))}")

    return df


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = SessionLocal()
    try:
        accounts = db.query(Account).order_by(Account.name.asc()).all()

        last_market_update = (
            db.query(MaintenanceLog)
            .filter(
                MaintenanceLog.task_name == "market_price_update"
            )
            .order_by(
                MaintenanceLog.created_at.desc()
            )
            .first()
        )

        last_dividend_update = (
            db.query(MaintenanceLog)
            .filter(
                MaintenanceLog.task_name == "dividend_update"
            )
            .order_by(
                MaintenanceLog.created_at.desc()
            )
            .first()
        )

        return templates.TemplateResponse(
            "accounts.html",
            {
                "request": request,
                "title": "家庭投資收益管理",
                "accounts": accounts,
                "message": None,
                "last_market_update": last_market_update,
                "last_dividend_update": last_dividend_update,
            },
        )
    finally:
        db.close()


@router.post("/accounts", response_class=HTMLResponse)
async def create_account(request: Request, account_name: str = Form(...)):
    db = SessionLocal()
    try:
        name = account_name.strip()
        if not name:
            accounts = db.query(Account).order_by(Account.name.asc()).all()
            return templates.TemplateResponse(
                "accounts.html",
                {
                    "request": request,
                    "title": "家庭投資收益管理",
                    "accounts": accounts,
                    "message": "帳戶名稱不可空白",
                },
                status_code=400,
            )

        account = Account(name=name)
        db.add(account)
        db.commit()
        return RedirectResponse(url="/", status_code=303)
    except IntegrityError:
        db.rollback()
        accounts = db.query(Account).order_by(Account.name.asc()).all()
        return templates.TemplateResponse(
            "accounts.html",
            {
                "request": request,
                "title": "家庭投資收益管理",
                "accounts": accounts,
                "message": f"帳戶 {account_name} 已存在",
            },
            status_code=400,
        )
    finally:
        db.close()


@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail(request: Request, account_id: int):
    db = SessionLocal()
    try:
        context = build_account_detail_context(
            request=request,
            db=db,
            account_id=account_id,
            message=None,
        )

        if context is None:
            return HTMLResponse("Account not found", status_code=404)

        return templates.TemplateResponse(
            "account_detail.html",
            context,
        )
    finally:
        db.close()


def build_account_detail_context(
    request: Request,
    db,
    account_id: int,
    message: str | None = None,
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return None

    transactions = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
        .all()
    )

    summary = calculate_account_summary(transactions)
    positions = calculate_positions(transactions)

    benchmark = calculate_account_benchmark(account_id, db)

    holdings_performance = merge_positions_and_benchmark(
        positions=positions,
        benchmark=benchmark,
    )

    performance_rows = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == account_id)
        .order_by(MonthlyPerformance.year_month.desc())
        .all()
    )

    latest_month = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == account_id)
        .order_by(MonthlyPerformance.year_month.desc())
        .first()
    )

    latest_performance = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == account_id)
        .order_by(MonthlyPerformance.created_at.desc())
        .first()
    )

    last_rebuilt_at = (
        latest_performance.created_at
        if latest_performance
        else None
    )

    holding_years = None
    annualized_return = None

    first_trade_date = summary.get("first_trade_date")

    if latest_month and first_trade_date:
        try:
            first_date = datetime.strptime(
                first_trade_date,
                "%Y/%m/%d",
            )

            today = datetime.today()
            holding_days = (today - first_date).days
            holding_years = holding_days / 365.25

            if (
                holding_years > 0
                and latest_month.total_cost > 0
                and latest_month.market_value > 0
            ):
                annualized_return = (
                    (latest_month.market_value / latest_month.total_cost)
                    ** (1 / holding_years)
                    - 1
                )

        except Exception:
            holding_years = None
            annualized_return = None

    return {
        "request": request,
        "title": f"帳戶管理 - {account.name}",
        "account": account,
        "transactions": transactions,
        "summary": summary,
        "positions": positions,
        "performance_rows": performance_rows,
        "message": message,
        "last_rebuilt_at": last_rebuilt_at,
        "latest_month": latest_month,
        "holding_years": holding_years,
        "annualized_return": annualized_return,
        "benchmark": benchmark,
        "holdings_performance": holdings_performance,
    }


def rebuild_account_data(db, account_id: int):
    holdings_result = rebuild_monthly_holdings(
        account_id=account_id,
        db=db,
    )

    performance_result = rebuild_monthly_performance(
        account_id=account_id,
        db=db,
    )

    return {
        "holdings": holdings_result,
        "performance": performance_result,



@router.post("/accounts/{account_id}/upload", response_class=HTMLResponse)
async def upload_transactions(
    request: Request,
    account_id: int,
    file: UploadFile = File(...),
):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return HTMLResponse("Account not found", status_code=404)

        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            return HTMLResponse("只接受 .csv 檔案", status_code=400)

        contents = await file.read()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_name = f"{account.name}_{timestamp}_{Path(filename).name}"
        save_path = UPLOAD_DIR / save_name
        save_path.write_bytes(contents)

        df = read_broker_csv(contents)

        inserted_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            order_id = str(row["委託書號"]).strip()

            existed = (
                db.query(Transaction)
                .filter(
                    Transaction.account_id == account_id,
                    Transaction.trade_date == str(row["日期"]).strip(),
                    Transaction.order_id == order_id,
                )
                .first()
            )

            if existed:
                skipped_count += 1
                continue

            side_text = str(row["買賣別"]).strip()
            side = "BUY" if "買" in side_text else "SELL"

            tx = Transaction(
                account_id=account_id,
                stock_name=str(row["股名"]).strip(),
                trade_date=str(row["日期"]).strip(),
                side=side,
                quantity=clean_number(row["成交股數"]),
                price=clean_number(row["成交價"]),
                cost=clean_number(row["成本"]),
                net_amount=clean_number(row["淨收付金額"]),
                fee=clean_number(row["手續費"]),
                tax=clean_number(row["交易稅"]),
                order_id=order_id,
                source_file=save_name,
            )
            db.add(tx)
            inserted_count += 1

        db.commit()

        try:
            rebuild_result = rebuild_account_data(db, account_id)
            db.commit()

            message = (
                f"匯入完成：新增 {inserted_count} 筆，"
                f"略過 {skipped_count} 筆重複資料，"
                f"並已自動重建績效資料。"
            )

        except Exception as rebuild_exc:
            db.rollback()

            message = (
                f"匯入完成：新增 {inserted_count} 筆，"
                f"略過 {skipped_count} 筆重複資料，"
                f"但自動重建績效資料失敗：{rebuild_exc}。"
                f"請手動執行重建。"
            )

        context = build_account_detail_context(
            request=request,
            db=db,
            account_id=account_id,
            message=message,
        )

        if context is None:
            return HTMLResponse("Account not found", status_code=404)

        return templates.TemplateResponse(
            "account_detail.html",
            context,
        )

    except Exception as exc:
        db.rollback()

        context = build_account_detail_context(
            request=request,
            db=db,
            account_id=account_id,
            message=f"匯入失敗：{exc}",
        )

        if context is None:
            return HTMLResponse("Account not found", status_code=404)

        return templates.TemplateResponse(
            "account_detail.html",
            context,
            status_code=400,
        )

    finally:
        db.close()


@router.post("/accounts/{account_id}/rebuild")
async def rebuild_account_performance(
    request: Request,
    account_id: int,
):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return HTMLResponse("Account not found", status_code=404)


        rebuild_result = rebuild_account_data(db, account_id)
        holdings_result = rebuild_result["holdings"]
        performance_result = rebuild_result["performance"]

        result = {
            "帳戶": account.name,
            "交易筆數": holdings_result.get("transactions", 0),
            "Monthly Holdings": holdings_result.get("snapshots_created", 0),
            "Monthly Performance": performance_result.get("rows_created", 0),
        }

        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "帳戶績效重建完成",
                "success": True,
                "result": result,
                "message": f"{account.name} 帳戶績效資料已完成重建",
                "back_url": f"/accounts/{account_id}",
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            "maintenance_result.html",
            {
                "request": request,
                "title": "帳戶績效重建失敗",
                "success": False,
                "result": {},
                "message": str(exc),
                "back_url": f"/accounts/{account_id}",
            },
            status_code=500,
        )

    finally:
        db.close()
