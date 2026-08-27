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
    non-empty metadata; a stored full description is never replaced with an
    empty or shorter value.
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
        updated += 1

    session.commit()
    logger.info(
        "Saved fetched jobs: created=%s updated=%s skipped=%s",
        created,
        updated,
        skipped,
    )
    return SaveSummary(created=created, skipped=skipped, updated=updated)
