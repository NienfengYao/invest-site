from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
