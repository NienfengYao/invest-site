from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.monthly_price import MonthlyPrice
from app.models.transaction import Transaction

STOCK_NAME_TO_TICKER = {
    "富邦台50": "006208",
    "國泰永續高股息": "00878",
    "元大台灣50": "0050",
    "元大高股息": "0056",
    "群益台灣精選高息": "00919",
    "復華台灣科技優息": "00929",
    "國泰10Y+金融債": "00933B",
    "元大美債20年": "00679B",
    "元大美債20正2": "00680L",
    "主動群益台灣強棒": "00982A",
    "國泰台灣領袖50": "00922",
    "富邦特選高股息30": "00900",
}


def resolve_ticker(stock_name: str) -> Optional[str]:
    name = stock_name.strip()
    if not name:
        return None

    # 若原本就是代號，直接回傳
    upper_name = name.upper()
    if upper_name.isdigit():
        return upper_name

    if upper_name.endswith(".TW") or upper_name.endswith(".TWO"):
        return upper_name

    # 中文股名轉 ticker
    return STOCK_NAME_TO_TICKER.get(name)


def parse_trade_date(date_str: str) -> datetime:
    """
    目前交易日期先支援幾種常見格式
    """
    formats = [
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    raise ValueError(f"Unsupported trade_date format: {date_str}")


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    month += delta

    while month <= 0:
        month += 12
        year -= 1

    while month > 12:
        month -= 12
        year += 1

    return year, month


def get_required_tickers_with_start(db: Session) -> Dict[str, datetime]:
    """
    從交易資料推導每檔股票需要抓取的起始日期：
    ticker -> 最早交易日期
    """
    result: Dict[str, List[datetime]] = defaultdict(list)

    txs = db.query(Transaction).all()

    for tx in txs:
        try:
            trade_dt = parse_trade_date(tx.trade_date)
            # ticker = tx.stock_name.strip()
            ticker = resolve_ticker(tx.stock_name)
            if ticker:
                result[ticker].append(trade_dt)
            else:
                print(f"[market_data] unresolved stock_name: {tx.stock_name}")
        except ValueError as exc:
            print(f"[market_data] skip invalid trade_date: {tx.trade_date}, error: {exc}")

    output: Dict[str, datetime] = {}
    for ticker, dates in result.items():
        output[ticker] = min(dates)

    return output


def get_fetch_start_date(first_trade_dt: datetime) -> str:
    """
    抓取起點 = 最早交易月份的前一個月 1 號
    例如：
    2024-01-15 -> 2023-12-01
    """
    year, month = shift_month(first_trade_dt.year, first_trade_dt.month, -1)
    return f"{year}-{month:02d}-01"


def normalize_yf_ticker(ticker: str) -> str:
    """
    簡單規則：
    - 純數字視為台股，補 .TW
    - 其他先原樣使用
    """
    t = ticker.strip().upper()
    if t.isdigit():
        return f"{t}.TW"
    return t


def safe_download(yf_ticker: str, start_date: str) -> Optional[pd.DataFrame]:
    """
    安全下載：
    - 關閉 threads
    - 關閉 progress
    - auto_adjust=False
    - 加 sleep 避免過快請求
    """
    try:
        time.sleep(1.0)

        df = yf.download(
            yf_ticker,
            start=start_date,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            print(f"[market_data] empty data for {yf_ticker}")
            return None

        return df
    except Exception as exc:
        print(f"[market_data] download failed for {yf_ticker}: {exc}")
        return None


def download_with_retry(yf_ticker: str, start_date: str, retries: int = 3) -> Optional[pd.DataFrame]:
    for attempt in range(1, retries + 1):
        df = safe_download(yf_ticker, start_date)
        if df is not None and not df.empty:
            return df

        print(f"[market_data] retry {attempt}/{retries} for {yf_ticker}")
        time.sleep(2.0)

    return None


def to_monthly_close(df: pd.DataFrame) -> pd.DataFrame:
    """
    將日線轉為每月月底收盤價
    """
    monthly = df.resample("ME").last().copy()

    # yfinance 有時欄位會是 MultiIndex，這裡做保守處理
    if isinstance(monthly.columns, pd.MultiIndex):
        if ("Close", "") in monthly.columns:
            monthly = monthly[[("Close", "")]].copy()
            monthly.columns = ["Close"]
        else:
            close_cols = [col for col in monthly.columns if col[0] == "Close"]
            if close_cols:
                monthly = monthly[[close_cols[0]]].copy()
                monthly.columns = ["Close"]

    if "Close" not in monthly.columns:
        raise ValueError("Close column not found after resample")

    monthly = monthly.dropna(subset=["Close"])
    return monthly[["Close"]]


def fetch_and_store_monthly_prices(db: Session) -> dict:
    """
    核心流程：
    1. 從交易資料推導 ticker 與起始日期
    2. 查 DB 已有哪些月份
    3. 下載缺漏資料
    4. 轉成月底收盤價
    5. 寫入 monthly_prices
    """
    ticker_map = get_required_tickers_with_start(db)

    summary = {
        "total_tickers": 0,
        "success_tickers": 0,
        "failed_tickers": [],
        "inserted_rows": 0,
    }

    if not ticker_map:
        return summary

    summary["total_tickers"] = len(ticker_map)

    for ticker, first_trade_dt in ticker_map.items():
        try:
            start_date = get_fetch_start_date(first_trade_dt)
            yf_ticker = normalize_yf_ticker(ticker)

            existing_rows = (
                db.query(MonthlyPrice)
                .filter(MonthlyPrice.ticker == ticker)
                .all()
            )
            existing_months = {row.year_month for row in existing_rows}

            df = download_with_retry(yf_ticker, start_date, retries=3)
            if df is None or df.empty:
                summary["failed_tickers"].append(ticker)
                continue

            monthly_df = to_monthly_close(df)

            inserted_for_ticker = 0

            for idx, row in monthly_df.iterrows():
                year_month = idx.strftime("%Y-%m")

                if year_month in existing_months:
                    continue

                price = row["Close"]
                if pd.isna(price):
                    continue

                monthly_price = MonthlyPrice(
                    ticker=ticker,
                    year_month=year_month,
                    month_end_date=idx.date(),
                    close_price=float(price),
                )
                db.add(monthly_price)
                inserted_for_ticker += 1

            db.commit()

            summary["success_tickers"] += 1
            summary["inserted_rows"] += inserted_for_ticker

            print(
                f"[market_data] ticker={ticker}, yf_ticker={yf_ticker}, "
                f"start_date={start_date}, inserted={inserted_for_ticker}"
            )

        except Exception as exc:
            db.rollback()
            summary["failed_tickers"].append(ticker)
            print(f"[market_data] failed ticker={ticker}, error={exc}")

    return summary
