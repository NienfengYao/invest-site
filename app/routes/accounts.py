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
from app.services.account_summary import (
    calculate_account_summary,
    calculate_account_monthly_summary,
    calculate_positions,
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
        return templates.TemplateResponse(
            "accounts.html",
            {
                "request": request,
                "title": "家庭投資收益管理",
                "accounts": accounts,
                "message": None,
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
async def account_detail(request: Request, account_id: int, sort_by: str = "date"):
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return HTMLResponse("Account not found", status_code=404)

        query = db.query(Transaction).filter(Transaction.account_id == account_id)

        if sort_by == "stock":
            transactions = query.order_by(Transaction.stock_name.asc(), Transaction.trade_date.asc()).all()
        else:
            transactions = query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()).all()

        summary = calculate_account_summary(transactions)
        positions = calculate_positions(transactions)

        monthly_prices = (
            db.query(MonthlyPrice)
            .order_by(MonthlyPrice.year_month.asc(), MonthlyPrice.ticker.asc())
            .all()
        )
        monthly_summary = calculate_account_monthly_summary(transactions, monthly_prices)

        return templates.TemplateResponse(
            "account_detail.html",
            {
                "request": request,
                "title": f"帳戶管理 - {account.name}",
                "account": account,
                "transactions": transactions,
                "summary": summary,
                "positions": positions,
                "monthly_summary": monthly_summary,
                "sort_by": sort_by,
                "message": None,
            },
        )
    finally:
        db.close()


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

        query = db.query(Transaction).filter(Transaction.account_id == account_id)
        transactions = query.order_by(Transaction.trade_date.desc(), Transaction.id.desc()).all()

        summary = calculate_account_summary(transactions)
        positions = calculate_positions(transactions)

        monthly_prices = (
            db.query(MonthlyPrice)
            .order_by(MonthlyPrice.year_month.asc(), MonthlyPrice.ticker.asc())
            .all()
        )
        monthly_summary = calculate_account_monthly_summary(transactions, monthly_prices)

        return templates.TemplateResponse(
            "account_detail.html",
            {
                "request": request,
                "title": f"帳戶管理 - {account.name}",
                "account": account,
                "transactions": transactions,
                "summary": summary,
                "positions": positions,
                "monthly_summary": monthly_summary,
                "sort_by": "date",
                "message": f"匯入完成：新增 {inserted_count} 筆，略過 {skipped_count} 筆重複資料",
            },
        )
    except Exception as exc:
        db.rollback()
        account = db.query(Account).filter(Account.id == account_id).first()
        transactions = (
            db.query(Transaction)
            .filter(Transaction.account_id == account_id)
            .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
            .all()
        )
        summary = calculate_account_summary(transactions)
        positions = calculate_positions(transactions)

        return templates.TemplateResponse(
            "account_detail.html",
            {
                "request": request,
                "title": f"帳戶管理 - {account.name if account else account_id}",
                "account": account,
                "transactions": transactions,
                "summary": summary,
                "positions": positions,
                "sort_by": "date",
                "message": f"匯入失敗：{exc}",
            },
            status_code=400,
        )
    finally:
        db.close()
