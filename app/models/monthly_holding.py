# app/models/monthly_holding.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db import Base


class MonthlyHolding(Base):
    __tablename__ = "monthly_holdings"

    id = Column(Integer, primary_key=True)

    account_id = Column(Integer, nullable=False, index=True)

    year_month = Column(String, nullable=False, index=True)

    ticker = Column(String, nullable=False, index=True)

    shares = Column(Float, nullable=False, default=0)

    avg_cost = Column(Float, nullable=False, default=0)

    total_cost = Column(Float, nullable=False, default=0)

    market_price = Column(Float, nullable=True)

    market_value = Column(Float, nullable=True)

    unrealized_gain = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "year_month",
            "ticker",
            name="uq_monthly_holding",
        ),
    )
