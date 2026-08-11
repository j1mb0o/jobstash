from src.repositories.jobs import JobRepository
from src.schemas.job import JobDetail, JobListItem


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def list_jobs(self) -> list[JobListItem]:
        return [JobListItem.model_validate(job) for job in self.repository.list_jobs()]

    def get_job(self, job_id: int) -> JobDetail | None:
        job = self.repository.get_job(job_id)
        return JobDetail.model_validate(job) if job is not None else None
