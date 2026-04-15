from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False)

    trade_date = Column(String(20))
    stock_name = Column(String(100))

    quantity = Column(Float)
    price = Column(Float)
    cost = Column(Float)

    net_amount = Column(Float)
    fee = Column(Float)
    tax = Column(Float)

    side = Column(String(10))
    order_id = Column(String(50))

    source_file = Column(String(100))
    created_at = Column(DateTime)
