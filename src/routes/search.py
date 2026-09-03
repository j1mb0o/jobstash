import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.schemas.search import (
    ExperienceLevel,
    JobType,
    SearchFilters,
    Seniority,
    TimePosted,
    WorkModel,
    labels_for,
    optional_labels_for,
)
from src.services.jobs import known_job_ids_with_description, save_records
from src.services.linkedin import LinkedInClient
from src.services.query_generation import (
    generate_queries,
    resolve_queries,
    split_lines_or_commas,
)
from src.services.scoring import (
    add_seniority_match_scores,
)

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class GenerateQueriesRequest(BaseModel):
    position_text: str
    seniority: Seniority = Seniority.junior


class GenerateQueriesResponse(BaseModel):
    queries: list[str]


def seniority_choices() -> list[tuple[str, str]]:
    """Seniority options with ``Any`` last so a real level is the default."""
    choices = labels_for(Seniority)
    return [c for c in choices if c[1] != Seniority.any.value] + [
        ("Any", Seniority.any.value)
    ]


class FetchJobsRequest(BaseModel):
    position_text: str
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


class FetchJobsResponse(BaseModel):
    new_jobs: int
    skipped: int
    updated: int
    already_stored: int
    cv_scored: int
    queries: list[str]
    message: str


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, settings: SettingsDependency) -> HTMLResponse:
    context = {
        "experience_choices": optional_labels_for(ExperienceLevel),
        "job_type_choices": optional_labels_for(JobType),
        "work_model_choices": optional_labels_for(WorkModel),
        "time_posted_choices": labels_for(TimePosted),
        "seniority_choices": seniority_choices(),
        "default_seniority": settings.default_seniority,
        "default_location": settings.default_location,
        "default_request_delay_seconds": settings.default_request_delay_seconds,
        "default_fetch_descriptions": settings.default_fetch_descriptions,
    }
    return templates.TemplateResponse(
        request=request, name="search.html", context=context
    )


@router.post("/search/queries", response_model=GenerateQueriesResponse)
def generate_queries_endpoint(
    payload: GenerateQueriesRequest,
) -> GenerateQueriesResponse:
    positions = split_lines_or_commas(payload.position_text)
    if not positions:
        return GenerateQueriesResponse(queries=[])
    return GenerateQueriesResponse(
        queries=generate_queries(positions, payload.seniority)
    )


@router.post("/search/fetch", response_model=FetchJobsResponse)
def fetch_jobs(
    payload: FetchJobsRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FetchJobsResponse:
    queries = resolve_queries(
        payload.position_text, payload.seniority, payload.query_text
    )
    if not queries:
        raise HTTPException(
            status_code=400, detail="Add at least one position or query."
        )

    filters = SearchFilters(
        location=payload.location.strip(),
        experience_level=payload.experience_level,
        job_type=payload.job_type,
        work_model=payload.work_model,
        time_posted=payload.time_posted,
        easy_apply=payload.easy_apply,
        under_10_applicants=payload.under_10_applicants,
    )

    known_ids = known_job_ids_with_description(session)
    logger.info(
        "Fetching LinkedIn jobs: queries=%s location=%s pages=%s include_details=%s detail_delay=%s known_jobs=%s",
        queries,
        filters.location,
        payload.max_pages,
        payload.include_details,
        payload.detail_delay_seconds,
        len(known_ids),
    )

    client = LinkedInClient(detail_delay_seconds=payload.detail_delay_seconds)
    try:
        outcome = client.search(
            queries=queries,
            filters=filters,
            seniority=payload.seniority,
            requested_positions=payload.position_text,
            max_pages_per_query=payload.max_pages,
            include_details=payload.include_details,
            status="New",
            skip_job_ids=known_ids,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("LinkedIn search failed with HTTP %s.", exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"LinkedIn returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("LinkedIn search failed.")
        raise HTTPException(status_code=502, detail="LinkedIn request failed.") from exc
    finally:
        client.close()

    records = add_seniority_match_scores(outcome.records)

    cv_scored = 0
    if not settings.openrouter_api_key:
        logger.info("CV scoring skipped: OPENROUTER_API_KEY is not configured.")
    else:
        cv_text = load_cv_text(settings.cv_path)
        if not cv_text:
            logger.warning(
                "CV scoring skipped: CV file %s is missing or empty.",
                settings.cv_path,
            )
        else:
            cv_client = OpenRouterClient(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
            )
            try:
                records = add_cv_match_scores(records, cv_client, cv_text)
            finally:
                cv_client.close()
            cv_scored = sum(record.cv_match_score is not None for record in records)
            logger.info(
                "CV scoring finished: %s of %s records scored.",
                cv_scored,
                len(records),
            )

    records = add_final_scores(records)
    summary = save_records(records, session)
    return FetchJobsResponse(
        new_jobs=summary.created,
        skipped=summary.skipped,
        updated=summary.updated,
        already_stored=outcome.skipped_known,
        cv_scored=cv_scored,
        queries=queries,
        message=(
            f"{summary.created} new, {outcome.skipped_known} already stored, "
            f"{summary.skipped} duplicates skipped, {summary.updated} updated."
        ),
    )
