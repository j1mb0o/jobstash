import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.job import Job
from src.repositories.jobs import JobRepository
from src.schemas.search import JobRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SaveSummary:
    created: int
    skipped: int
    updated: int


@dataclass(frozen=True)
class BulkActionSummary:
    matched: int
    deleted: int = 0
    updated: int = 0


def known_job_ids_with_description(session: Session) -> set[str]:
    """LinkedIn job IDs already stored with a full description.

    Fetches can skip these jobs entirely: their content is already preserved
    and re-processing them would only repeat detail requests. Jobs stored
    without a description are not returned so a later fetch can repair them.
    """
    return JobRepository(session).linkedin_job_ids_with_description()


def job_from_record(record: JobRecord) -> Job:
    flat = record.to_flat_dict()
    return Job(
        linkedin_job_id=str(flat["linkedin_job_id"]),
        title=str(flat["title"]),
        company=str(flat["company"]),
        location=str(flat["location"]),
        work_model=str(flat["work_model"]),
        job_type=str(flat["job_type"]),
        experience_level=str(flat["experience_level"]),
        posted_at=None,
        post_time=str(flat["post_time"]),
        applicants=0,
        seniority=str(flat["seniority"]),
        requested_positions=str(flat["requested_positions"]),
        search_query=str(flat["search_query"]),
        status=str(flat["status"]) or "New",
        url=str(flat["url"]),
        description=str(flat["description"]),
        criteria=str(flat["criteria"]),
        seniority_match_score=flat.get("seniority_match_score"),  # type: ignore[arg-type]
    )


def should_preserve_description(existing: Job, incoming: str) -> bool:
    """Keep the existing description when the incoming one is empty or shorter."""
    if not incoming:
        return True
    if not existing.description:
        return False
    return len(existing.description) >= len(incoming)


def save_records(records: list[JobRecord], session: Session) -> SaveSummary:
    """Persist fetched records, skipping duplicates and preserving descriptions.

    A record is considered a duplicate when a job with the same
    ``linkedin_job_id`` already exists. Existing rows are updated only with
    a longer incoming description; scores are refreshed alongside it. A
    stored full description is never replaced with an empty or shorter value.
    """
    repository = JobRepository(session)
    created = 0
    skipped = 0
    updated = 0

    for record in records:
        if not record.job_id:
            logger.warning("Skipping record without job_id: %s", record.title)
            continue

        existing = repository.get_by_linkedin_job_id(record.job_id)
        if existing is None:
            repository.add(job_from_record(record))
            created += 1
            continue

        incoming_description = record.details.description
        if should_preserve_description(existing, incoming_description):
            skipped += 1
            continue

        existing.description = incoming_description
        existing.seniority_match_score = (
            record.seniority_match_score
            if record.seniority_match_score is not None
            else existing.seniority_match_score
        )
        updated += 1

    session.commit()
    logger.info(
        "Saved fetched jobs: created=%s updated=%s skipped=%s",
        created,
        updated,
        skipped,
    )
    return SaveSummary(created=created, skipped=skipped, updated=updated)


def update_job_status(session: Session, job_id: int, status: str) -> Job | None:
    """Update a single job's status, returning None when the job is missing."""
    repository = JobRepository(session)
    stored_job = repository.update_status(job_id, status)
    if stored_job is None:
        return None
    session.commit()
    session.refresh(stored_job)
    logger.info("Updated job status: job_id=%s status=%s", job_id, status)
    return stored_job


def delete_job(session: Session, job_id: int) -> bool:
    """Delete a single job, returning False when the job is missing."""
    deleted = JobRepository(session).delete_job(job_id)
    if deleted:
        session.commit()
        logger.info("Deleted job: job_id=%s", job_id)
    return deleted


def bulk_delete_jobs(session: Session, job_ids: list[int]) -> BulkActionSummary:
    """Delete the selected jobs, ignoring unknown IDs."""
    deleted = JobRepository(session).bulk_delete(job_ids)
    session.commit()
    logger.info("Bulk deleted jobs: requested=%s deleted=%s", len(job_ids), deleted)
    return BulkActionSummary(matched=len(job_ids), deleted=deleted)


def bulk_update_job_status(
    session: Session, job_ids: list[int], status: str
) -> BulkActionSummary:
    """Update the status of the selected jobs, ignoring unknown IDs."""
    updated = JobRepository(session).bulk_update_status(job_ids, status)
    session.commit()
    logger.info(
        "Bulk updated job status: requested=%s updated=%s status=%s",
        len(job_ids),
        updated,
        status,
    )
    return BulkActionSummary(matched=len(job_ids), updated=updated)


def get_jobs_for_export(session: Session, job_ids: list[int] | None) -> list[Job]:
    """Jobs to export: the selected IDs, or all stored jobs when omitted."""
    repository = JobRepository(session)
    if job_ids:
        stored_jobs = repository.get_jobs_by_ids(sorted(set(job_ids)))
        return sorted(stored_jobs, key=lambda job: job.id)
    return repository.list_jobs()
