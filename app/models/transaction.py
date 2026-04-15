from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "order_id", name="uq_transactions_account_order"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)

    stock_name = Column(String(100), nullable=False, index=True)
    trade_date = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)

    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=True)
    net_amount = Column(Float, nullable=True)
    fee = Column(Float, nullable=True)
    tax = Column(Float, nullable=True)

    order_id = Column(String(50), nullable=True)
    source_file = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
