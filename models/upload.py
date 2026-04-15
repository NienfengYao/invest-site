from fastapi import APIRouter, UploadFile, File, Form
import pandas as pd
from datetime import datetime
from io import BytesIO

from app.db import SessionLocal
from sqlalchemy import text

router = APIRouter()


def clean_number(x):
    if pd.isna(x):
        return 0
    return float(str(x).replace(",", ""))


@router.post("/upload")
async def upload_csv(
    account_id: int = Form(...),
    file: UploadFile = File(...)
):
    contents = await file.read()

    # 跳過第一行說明
    df = pd.read_csv(BytesIO(contents), skiprows=1)

    records = []

    for _, row in df.iterrows():
        side = "BUY" if row["買賣別"] == "現買" else "SELL"

        records.append({
            "account_id": account_id,
            "trade_date": row["日期"],
            "stock_name": row["股名"],
            "quantity": clean_number(row["成交股數"]),
            "price": clean_number(row["成交價"]),
            "cost": clean_number(row["成本"]),
            "net_amount": clean_number(row["淨收付金額"]),
            "fee": clean_number(row["手續費"]),
            "tax": clean_number(row["交易稅"]),
            "side": side,
            "order_id": row["委託書號"],
            "source_file": file.filename,
            "created_at": datetime.now()
        })

    db = SessionLocal()

    for r in records:
        db.execute(text("""
            INSERT INTO transactions (
                account_id, trade_date, stock_name,
                quantity, price, cost,
                net_amount, fee, tax,
                side, order_id,
                source_file, created_at
            )
            VALUES (
                :account_id, :trade_date, :stock_name,
                :quantity, :price, :cost,
                :net_amount, :fee, :tax,
                :side, :order_id,
                :source_file, :created_at
            )
        """), r)

    db.commit()
    db.close()

    return {"message": f"成功匯入 {len(records)} 筆資料"}
