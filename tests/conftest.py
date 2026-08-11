from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from src.models.job import Job


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'test-jobs.db'}"
    app = create_app(Settings(database_url=database_url))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def add_job(client: TestClient):
    def create(**overrides: object) -> Job:
        values = {
            "title": "Machine Learning Engineer",
            "company": "Northstar AI",
            "location": "Amsterdam",
            "work_model": "Hybrid",
            "job_type": "Full-time",
            "experience_level": "Entry level",
            "posted_at": datetime(2026, 8, 5, 10, 30, tzinfo=UTC),
            "applicants": 14,
            "status": "New",
            "url": "https://example.com/jobs/42",
            "description": "A locally preserved full description.",
        }
        values.update(overrides)
        job = Job(**values)
        session_factory = client.app.state.session_factory
        with session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
        return job

    return create
