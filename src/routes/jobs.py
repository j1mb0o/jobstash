from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database import session_scope
from src.repositories.jobs import JobRepository
from src.schemas.job import JobListItem
from src.services.jobs import JobService

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


SessionDependency = Annotated[Session, Depends(get_session)]


def get_job_service(session: SessionDependency) -> JobService:
    return JobService(JobRepository(session))


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="jobs/list.html")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    request: Request,
    job_id: int,
    service: JobServiceDependency,
) -> HTMLResponse:
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return templates.TemplateResponse(
        request=request,
        name="jobs/detail.html",
        context={"job": job},
    )


@router.get("/api/jobs", response_model=list[JobListItem])
def list_jobs(service: JobServiceDependency) -> list[JobListItem]:
    return service.list_jobs()
