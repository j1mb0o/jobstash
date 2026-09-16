"""File-backed named search configuration (one JSON file per search)."""

from pydantic import BaseModel, Field

from src.schemas.search import (
    ExperienceLevel,
    JobType,
    Seniority,
    TimePosted,
    WorkModel,
)
from src.services.fetch_runner import FetchParams


class SearchConfig(BaseModel):
    """A named, serializable set of fetch inputs stored as ``configs/*.json``."""

    name: str = Field(min_length=1, max_length=80)
    position_text: str = ""
    seniority: Seniority = Seniority.junior
    query_text: str = ""
    location: str = ""
    experience_level: ExperienceLevel | None = None
    job_type: JobType | None = None
    work_model: WorkModel | None = None
    time_posted: TimePosted = TimePosted.any_time
    easy_apply: bool = False
    under_10_applicants: bool = False
    max_pages: int = Field(default=1, ge=1, le=10)
    include_details: bool = True
    detail_delay_seconds: float = Field(default=1.5, ge=0, le=30)

    def to_fetch_params(self) -> FetchParams:
        return FetchParams(
            position_text=self.position_text,
            seniority=self.seniority,
            query_text=self.query_text,
            location=self.location,
            experience_level=self.experience_level,
            job_type=self.job_type,
            work_model=self.work_model,
            time_posted=self.time_posted,
            easy_apply=self.easy_apply,
            under_10_applicants=self.under_10_applicants,
            max_pages=self.max_pages,
            include_details=self.include_details,
            detail_delay_seconds=self.detail_delay_seconds,
        )

    @classmethod
    def from_fetch_params(cls, name: str, params: FetchParams) -> "SearchConfig":
        return cls(name=name, **params.model_dump())
