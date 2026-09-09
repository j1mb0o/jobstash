from sqlalchemy import delete, select
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

    def linkedin_job_ids_with_description(self) -> set[str]:
        """LinkedIn job IDs of stored jobs that already have a description.

        Jobs stored without a description are excluded so a later fetch can
        still repair them.
        """
        statement = select(Job.linkedin_job_id).where(
            Job.linkedin_job_id.is_not(None), Job.description != ""
        )
        return set(self.session.scalars(statement).all())

    def add(self, job: Job) -> Job:
        self.session.add(job)
        self.session.flush()
        return job

    def get_jobs_by_ids(self, job_ids: list[int]) -> list[Job]:
        if not job_ids:
            return []
        statement = select(Job).where(Job.id.in_(job_ids))
        return list(self.session.scalars(statement).all())

    def update_status(self, job_id: int, status: str) -> Job | None:
        stored_job = self.session.get(Job, job_id)
        if stored_job is None:
            return None
        stored_job.status = status
        self.session.flush()
        return stored_job

    def delete_job(self, job_id: int) -> bool:
        stored_job = self.session.get(Job, job_id)
        if stored_job is None:
            return False
        self.session.delete(stored_job)
        self.session.flush()
        return True

    def bulk_delete(self, job_ids: list[int]) -> int:
        unique_ids = sorted(set(job_ids))
        if not unique_ids:
            return 0
        statement = delete(Job).where(Job.id.in_(unique_ids))
        result = self.session.execute(statement)
        self.session.flush()
        return int(result.rowcount or 0)

    def bulk_update_status(self, job_ids: list[int], status: str) -> int:
        unique_ids = sorted(set(job_ids))
        if not unique_ids:
            return 0
        statement = select(Job).where(Job.id.in_(unique_ids))
        stored_jobs = list(self.session.scalars(statement).all())
        for stored_job in stored_jobs:
            stored_job.status = status
        self.session.flush()
        return len(stored_jobs)
