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
    Seniority,
    TimePosted,
    WorkModel,
    labels_for,
)
from src.schemas.search_config import SearchConfig
from src.services.fetch_runner import EmptyQueryError, FetchParams, run_fetch
from src.services.linkedin import LinkedInClient
from src.services.query_generation import (
    generate_queries,
    split_lines_or_commas,
)
from src.services.search_configs import (
    SearchConfigError,
    list_config_names,
    load_config_by_name,
    save_config,
    slugify_name,
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
    discarded_seniority: int
    queries: list[str]
    message: str


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, settings: SettingsDependency) -> HTMLResponse:
    context = {
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
    params = FetchParams(**payload.model_dump())
    try:
        summary = run_fetch(params, session, client_factory=LinkedInClient)
    except EmptyQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("LinkedIn search failed with HTTP %s.", exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"LinkedIn returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("LinkedIn search failed.")
        raise HTTPException(status_code=502, detail="LinkedIn request failed.") from exc
    return FetchJobsResponse(
        new_jobs=summary.new_jobs,
        skipped=summary.skipped,
        updated=summary.updated,
        already_stored=summary.already_stored,
        discarded_seniority=summary.discarded_seniority,
        queries=summary.queries,
        message=summary.message,
    )


def _config_dir(settings: Settings) -> Path:
    return Path(settings.search_config_dir)


class SearchConfigListResponse(BaseModel):
    configs: list[str]


@router.get("/api/search-configs", response_model=SearchConfigListResponse)
def list_search_configs(settings: SettingsDependency) -> SearchConfigListResponse:
    return SearchConfigListResponse(configs=list_config_names(_config_dir(settings)))


@router.get("/api/search-configs/{name}", response_model=SearchConfig)
def get_search_config(name: str, settings: SettingsDependency) -> SearchConfig:
    try:
        slugify_name(name)
        return load_config_by_name(_config_dir(settings), name)
    except SearchConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class SaveSearchConfigResponse(BaseModel):
    name: str
    file: str


@router.post("/api/search-configs", response_model=SaveSearchConfigResponse)
def store_search_config(
    payload: SearchConfig, settings: SettingsDependency
) -> SaveSearchConfigResponse:
    try:
        path = save_config(_config_dir(settings), payload)
    except SearchConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Saved search config: name=%s file=%s", payload.name, path)
    return SaveSearchConfigResponse(name=payload.name, file=path.name)
