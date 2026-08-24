import logging
from collections.abc import Iterator
from pathlib import Path
from random import randint
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.services.seed import create_random_job_payload

logger = logging.getLogger(__name__)

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


class FetchResult(BaseModel):
    new_jobs: int


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="search.html")


@router.post("/search/fetch", response_model=FetchResult)
def fetch_jobs(session: SessionDependency) -> FetchResult:
    from src.models.job import Job

    largest_id = session.query(Job.id).order_by(Job.id.desc()).first()
    largest_id = largest_id[0] if largest_id else 0

    count = randint(2, 8)  # Generate random jobs per fetch for testing
    jobs = [
        Job(**create_random_job_payload(largest_id + offset))
        for offset in range(1, count + 1)
    ]
    session.add_all(jobs)
    session.commit()

    return FetchResult(new_jobs=count)
