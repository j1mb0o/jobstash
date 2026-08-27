from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.job import Job


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_jobs(self) -> list[Job]:
        statement = select(Job).order_by(Job.posted_at.desc(), Job.id.desc())
        return list(self.session.scalars(statement).all())

    def get_job(self, job_id: int) -> Job | None:
        return self.session.get(Job, job_id)

    def get_by_linkedin_job_id(self, linkedin_job_id: str) -> Job | None:
        statement = select(Job).where(Job.linkedin_job_id == linkedin_job_id)
        return self.session.scalars(statement).first()

    def add(self, job: Job) -> Job:
        self.session.add(job)
        self.session.flush()
        return job
