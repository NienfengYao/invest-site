from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.market_data import fetch_and_store_monthly_prices

router = APIRouter(tags=["market"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/update-market-data")
def update_market_data(db: Session = Depends(get_db)):
    result = fetch_and_store_monthly_prices(db)
    return {
        "status": "ok",
        "result": result,
    }
