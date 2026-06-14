from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func

from app.db import Base


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id = Column(Integer, primary_key=True)

    task_name = Column(String, nullable=False, index=True)

    success = Column(Boolean, nullable=False, default=True)

    message = Column(Text, nullable=True)

    created_count = Column(Integer, nullable=False, default=0)

    updated_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
