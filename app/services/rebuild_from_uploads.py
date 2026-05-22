# app/services/rebuild_from_uploads.py

from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.monthly_holding import MonthlyHolding
from app.models.monthly_performance import MonthlyPerformance

from app.routes.accounts import read_broker_csv, clean_number

from app.services.cost_engine import rebuild_monthly_holdings
from app.services.performance_engine import rebuild_monthly_performance


UPLOAD_DIR = Path("/site/data/uploads")


def _find_account_csv_files(account_name: str):
    account_key = account_name.strip().lower()

    return [
        csv_file
        for csv_file in sorted(UPLOAD_DIR.glob("*.csv"))
        if account_key in csv_file.name.lower()
    ]


def _delete_account_data(account_id: int, db: Session) -> dict:
    deleted = {}

    deleted["transactions"] = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id)
        .delete()
    )

    deleted["monthly_holdings"] = (
        db.query(MonthlyHolding)
        .filter(MonthlyHolding.account_id == account_id)
        .delete()
    )

    deleted["monthly_performance"] = (
        db.query(MonthlyPerformance)
        .filter(MonthlyPerformance.account_id == account_id)
        .delete()
    )

    db.flush()

    return deleted


def _import_one_csv(
    account_id: int,
    csv_file: Path,
    db: Session,
) -> dict:
    contents = csv_file.read_bytes()

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
            source_file=csv_file.name,
        )

        db.add(tx)
        inserted_count += 1

    return {
        "file": csv_file.name,
        "inserted": inserted_count,
        "skipped": skipped_count,
    }


def rebuild_from_uploads(
    account_id: int,
    db: Session,
):
    account = (
        db.query(Account)
        .filter(Account.id == account_id)
        .first()
    )

    if not account:
        return {
            "account_id": account_id,
            "error": "Account not found.",
        }

    csv_files = _find_account_csv_files(account.name)

    if not csv_files:
        return {
            "account_id": account_id,
            "account_name": account.name,
            "upload_dir": str(UPLOAD_DIR),
            "message": "No matching CSV files found.",
        }

    result = {
        "account_id": account_id,
        "account_name": account.name,
        "matched_files": [f.name for f in csv_files],
        "deleted": {},
        "imported_files": [],
        "holdings": None,
        "performance": None,
    }

    try:
        result["deleted"] = _delete_account_data(
            account_id=account_id,
            db=db,
        )

        for csv_file in csv_files:
            import_result = _import_one_csv(
                account_id=account_id,
                csv_file=csv_file,
                db=db,
            )
            result["imported_files"].append(import_result)

        db.commit()

    except IntegrityError as exc:
        db.rollback()
        result["error"] = f"IntegrityError: {exc}"
        return result

    except Exception as exc:
        db.rollback()
        result["error"] = str(exc)
        return result

    result["holdings"] = rebuild_monthly_holdings(
        account_id=account_id,
        db=db,
    )

    result["performance"] = rebuild_monthly_performance(
        account_id=account_id,
        db=db,
    )

    return result
