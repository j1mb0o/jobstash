from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    linkedin_job_id: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    work_model: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    experience_level: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    post_time: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    applicants: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seniority: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    requested_positions: Mapped[str] = mapped_column(
        String(200), nullable=False, default=""
    )
    search_query: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="New")
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criteria: Mapped[str] = mapped_column(Text, nullable=False, default="")
    seniority_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
