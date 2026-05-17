# app/models/monthly_performance.py

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


class MonthlyPerformance(Base):
    __tablename__ = "monthly_performance"

    id = Column(Integer, primary_key=True)

    account_id = Column(Integer, nullable=False, index=True)

    year_month = Column(String, nullable=False, index=True)

    buy_amount = Column(Float, nullable=False, default=0)

    sell_amount = Column(Float, nullable=False, default=0)

    dividend_amount = Column(Float, nullable=False, default=0)

    realized_gain = Column(Float, nullable=False, default=0)

    unrealized_gain = Column(Float, nullable=False, default=0)

    total_cost = Column(Float, nullable=False, default=0)

    market_value = Column(Float, nullable=False, default=0)

    total_return = Column(Float, nullable=False, default=0)

    return_rate = Column(Float, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "year_month",
            name="uq_monthly_performance",
        ),
    )
