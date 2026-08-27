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
    posted_at: datetime
    applicants: int
    url: str


class JobDetail(JobListItem):
    description: str
