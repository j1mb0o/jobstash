from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class JobStatus(str, Enum):
    """Allowed values for the user-editable job status field."""

    NEW = "New"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    REJECTED = "Rejected"


STATUS_OPTIONS: list[str] = [status.value for status in JobStatus]


def as_utc(value: datetime) -> datetime:
    """Attach UTC to naive datetimes read back from SQLite.

    The database stores UTC wall time, but SQLite drops the timezone marker,
    so values arrive here as naive datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str
    work_model: str
    job_type: str
    experience_level: str
    posted_at: datetime | None
    applicants: int
    seniority_match_score: int | None = None
    scraped_at: datetime
    url: str
    status: str = "New"

    @field_serializer("scraped_at")
    def _serialize_scraped_at(self, value: datetime) -> str:
        return as_utc(value).isoformat()


class JobDetail(JobListItem):
    linkedin_job_id: str | None = None
    post_time: str = ""
    seniority: str = ""
    requested_positions: str = ""
    search_query: str = ""
    description: str = ""
    criteria: str = ""

    @property
    def scraped_at_local(self) -> datetime:
        """Scraped time in the viewer's local timezone, for server-rendered pages."""
        return as_utc(self.scraped_at).astimezone()


class JobStatusUpdate(BaseModel):
    status: JobStatus


class BulkJobIds(BaseModel):
    job_ids: list[int] = Field(min_length=1)


class BulkStatusUpdate(BulkJobIds):
    status: JobStatus
