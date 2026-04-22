from datetime import datetime
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint
from app.db import Base


class MonthlyPrice(Base):
    __tablename__ = "monthly_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "year_month", name="uq_monthly_price"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True, nullable=False)
    year_month = Column(String(7), nullable=False)  # e.g. 2026-04
    month_end_date = Column(Date, nullable=False)
    close_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
