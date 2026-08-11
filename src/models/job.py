from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    work_model: Mapped[str] = mapped_column(String(50), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    applicants: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="New")
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
