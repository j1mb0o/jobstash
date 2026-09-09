from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.repositories.jobs import JobRepository
from src.schemas.job import (
    STATUS_OPTIONS,
    BulkJobIds,
    BulkStatusUpdate,
    JobDetail,
    JobListItem,
    JobStatusUpdate,
)
from src.services import jobs as jobs_service

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="jobs/list.html",
        context={"status_options": STATUS_OPTIONS},
    )


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
        context={
            "job": JobDetail.model_validate(stored_job),
            "status_options": STATUS_OPTIONS,
        },
    )


@router.get("/api/jobs", response_model=list[JobListItem])
def list_jobs(session: SessionDependency) -> list[JobListItem]:
    return [
        JobListItem.model_validate(stored_job)
        for stored_job in JobRepository(session).list_jobs()
    ]


@router.get("/api/jobs/export")
def export_jobs(
    session: SessionDependency,
    ids: Annotated[str | None, Query(description="Comma-separated job IDs")] = None,
) -> JSONResponse:
    job_ids: list[int] | None = None
    if ids:
        try:
            job_ids = [int(part) for part in ids.split(",") if part.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid job IDs for export.")
    stored_jobs = jobs_service.get_jobs_for_export(session, job_ids)
    payload = [
        JobDetail.model_validate(stored_job).model_dump(mode="json")
        for stored_job in stored_jobs
    ]
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": 'attachment; filename="jobs-export.json"'},
    )


@router.post("/api/jobs/bulk-delete")
def bulk_delete_jobs(payload: BulkJobIds, session: SessionDependency) -> dict[str, int]:
    summary = jobs_service.bulk_delete_jobs(session, payload.job_ids)
    return {"requested": summary.matched, "deleted": summary.deleted}


@router.patch("/api/jobs/bulk-status")
def bulk_update_job_status(
    payload: BulkStatusUpdate, session: SessionDependency
) -> dict[str, int | str]:
    summary = jobs_service.bulk_update_job_status(
        session, payload.job_ids, payload.status.value
    )
    return {
        "requested": summary.matched,
        "updated": summary.updated,
        "status": payload.status.value,
    }


@router.patch("/api/jobs/{job_id}", response_model=JobDetail)
def update_job_status(
    job_id: int,
    update: JobStatusUpdate,
    session: SessionDependency,
) -> JobDetail:
    stored_job = jobs_service.update_job_status(session, job_id, update.status.value)
    if stored_job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobDetail.model_validate(stored_job)


@router.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, session: SessionDependency) -> Response:
    if not jobs_service.delete_job(session, job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return Response(status_code=204)
