"""Shared LinkedIn fetch pipeline used by the web route and the CLI.

The FastAPI route previously owned this logic. It now lives here so
``POST /search/fetch`` and ``scripts/fetch_jobs.py`` cannot drift apart.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.schemas.search import (
    ExperienceLevel,
    JobType,
    SearchFilters,
    Seniority,
    TimePosted,
    WorkModel,
)
from src.services.jobs import SaveSummary, known_job_ids_with_description, save_records
from src.services.linkedin import LinkedInClient
from src.services.query_generation import resolve_queries
from src.services.scoring import (
    add_seniority_match_scores,
    filter_records_by_title,
    filter_records_within_seniority,
)

logger = logging.getLogger(__name__)


class FetchParams(BaseModel):
    """Validated fetch inputs, independent of HTTP or CLI transports."""

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
    max_pages: int = Field(default=1, ge=1)
    include_details: bool = True
    detail_delay_seconds: float = Field(default=1.5, ge=0)


@dataclass(frozen=True)
class FetchSummary:
    new_jobs: int
    skipped: int
    updated: int
    already_stored: int
    discarded_seniority: int
    queries: list[str]
    message: str


class EmptyQueryError(ValueError):
    """Raised when no position or query text resolves to a search query."""


ClientFactory = Callable[..., LinkedInClient]


def resolve_fetch_queries(params: FetchParams) -> list[str]:
    """Resolve editable queries without performing any network or DB work."""
    return resolve_queries(params.position_text, params.seniority, params.query_text)


def run_fetch(
    params: FetchParams,
    session: Session,
    client_factory: ClientFactory | None = None,
) -> FetchSummary:
    """Run one full fetch: search LinkedIn, score, persist, summarize.

    Raises:
        EmptyQueryError: when no query can be resolved.
        httpx2.HTTPStatusError / httpx2.HTTPError: LinkedIn request failures.
    """
    queries = resolve_fetch_queries(params)
    if not queries:
        raise EmptyQueryError("Add at least one position or query.")

    filters = SearchFilters(
        location=params.location.strip(),
        experience_level=params.experience_level,
        job_type=params.job_type,
        work_model=params.work_model,
        time_posted=params.time_posted,
        easy_apply=params.easy_apply,
        under_10_applicants=params.under_10_applicants,
    )

    known_ids = known_job_ids_with_description(session)
    logger.info(
        "Fetching LinkedIn jobs: queries=%s location=%s pages=%s "
        "include_details=%s detail_delay=%s known_jobs=%s",
        queries,
        filters.location,
        params.max_pages,
        params.include_details,
        params.detail_delay_seconds,
        len(known_ids),
    )

    factory: ClientFactory = client_factory or LinkedInClient
    client = factory(detail_delay_seconds=params.detail_delay_seconds)
    try:
        outcome = client.search(
            queries=queries,
            filters=filters,
            seniority=params.seniority,
            requested_positions=params.position_text,
            max_pages_per_query=params.max_pages,
            include_details=params.include_details,
            status="New",
            skip_job_ids=known_ids,
        )
    finally:
        client.close()

    records, discarded_title_records = filter_records_by_title(outcome.records)
    if discarded_title_records:
        logger.info(
            "Discarded %s jobs by title seniority mismatch (%s): %s",
            len(discarded_title_records),
            params.seniority.value,
            ", ".join(
                f"{record.title} ({record.job_id})"
                for record in discarded_title_records
            ),
        )

    records, discarded_records = filter_records_within_seniority(records)
    if discarded_records:
        logger.info(
            "Discarded %s jobs outside seniority tolerance (%s): %s",
            len(discarded_records),
            params.seniority.value,
            ", ".join(
                f"{record.title} ({record.job_id})" for record in discarded_records
            ),
        )

    discarded_seniority = (
        getattr(outcome, "discarded_title", 0)
        + len(discarded_title_records)
        + len(discarded_records)
    )

    records = add_seniority_match_scores(records)
    summary: SaveSummary = save_records(records, session)
    message = (
        f"{summary.created} new, {outcome.skipped_known} already stored, "
        f"{summary.skipped} duplicates skipped, {summary.updated} updated, "
        f"{discarded_seniority} discarded (experience mismatch)."
    )
    return FetchSummary(
        new_jobs=summary.created,
        skipped=summary.skipped,
        updated=summary.updated,
        already_stored=outcome.skipped_known,
        discarded_seniority=discarded_seniority,
        queries=queries,
        message=message,
    )


def describe_queries(
    queries: Iterable[str],
    filters: SearchFilters | None = None,
) -> list[str]:
    """Return the resolved query list as plain strings (for --dry-run output)."""
    return list(queries)
