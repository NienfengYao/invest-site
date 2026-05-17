# app/models/dividend.py

from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.sql import func

from app.db import Base


class Dividend(Base):
    __tablename__ = "dividends"

    id = Column(Integer, primary_key=True)

    ticker = Column(String, nullable=False, index=True)

    ex_dividend_date = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=True)

    dividend_per_share = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
