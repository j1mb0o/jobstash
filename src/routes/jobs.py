from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.repositories.jobs import JobRepository
from src.schemas.job import JobDetail, JobListItem

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="jobs/list.html")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    request: Request,
    job_id: int,
    session: SessionDependency,
) -> HTMLResponse:
    stored_job = JobRepository(session).get_job(job_id)
    if stored_job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return templates.TemplateResponse(
        request=request,
        name="jobs/detail.html",
        context={"job": JobDetail.model_validate(stored_job)},
    )


@router.get("/api/jobs", response_model=list[JobListItem])
def list_jobs(session: SessionDependency) -> list[JobListItem]:
    return [
        JobListItem.model_validate(stored_job)
        for stored_job in JobRepository(session).list_jobs()
    ]
