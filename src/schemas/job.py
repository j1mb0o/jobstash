from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class JobDetail(JobListItem):
    linkedin_job_id: str | None = None
    post_time: str = ""
    seniority: str = ""
    requested_positions: str = ""
    search_query: str = ""
    status: str = ""
    description: str = ""
    criteria: str = ""
