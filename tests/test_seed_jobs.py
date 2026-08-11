from sqlalchemy import func, select

from scripts.seed_jobs import add_sample_jobs
from src.models.job import Job


def test_add_sample_jobs_adds_requested_number(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session:
        total = add_sample_jobs(session, count=3)
        stored_count = session.scalar(select(func.count()).select_from(Job))

    assert total == 3
    assert stored_count == 3
