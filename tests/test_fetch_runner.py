from typing import Any

import pytest

from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services import fetch_runner as runner_module
from src.services.fetch_runner import EmptyQueryError, FetchParams, run_fetch
from src.services.linkedin import SearchResult


class FakeClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def search(self, **kwargs: Any) -> SearchResult:
        seniority = kwargs.get("seniority", Seniority.senior)
        return SearchResult(
            records=[
                JobRecord(
                    job_id="4123456789",
                    title="Machine Learning Engineer",
                    company="Example Co",
                    location="Amsterdam",
                    post_time="1 day ago",
                    url="https://www.linkedin.com/jobs/view/4123456789",
                    search_query="Senior ML Engineer",
                    seniority=seniority,
                    requested_positions="ML engineer",
                    status="New",
                    details=JobDetails(
                        description="Build ML systems.",
                        criteria={"Seniority level": "Mid-Senior level"},
                    ),
                )
            ],
            skipped_known=0,
        )

    def close(self) -> None:
        pass


def test_run_fetch_persists_and_summarizes(client) -> None:
    session_factory = client.app.state.session_factory
    params = FetchParams(
        position_text="ML engineer",
        seniority=Seniority.senior,
        query_text="Senior ML Engineer",
        detail_delay_seconds=0,
    )
    with session_factory() as session:
        summary = run_fetch(params, session, client_factory=FakeClient)
    assert summary.new_jobs == 1
    assert summary.queries == ["Senior ML Engineer"]
    assert "1 new" in summary.message
    assert client.get("/api/jobs").json()[0]["title"] == "Machine Learning Engineer"


def test_run_fetch_empty_queries_raise(client) -> None:
    session_factory = client.app.state.session_factory
    with session_factory() as session, pytest.raises(EmptyQueryError):
        run_fetch(
            FetchParams(position_text="  ", query_text=""),
            session,
            client_factory=FakeClient,
        )


def test_run_fetch_discards_junior_mismatch(client) -> None:
    session_factory = client.app.state.session_factory
    params = FetchParams(
        position_text="ML engineer",
        seniority=Seniority.junior,
        query_text="Junior ML Engineer",
        detail_delay_seconds=0,
    )
    with session_factory() as session:
        summary = run_fetch(params, session, client_factory=FakeClient)
    assert summary.new_jobs == 0
    assert summary.discarded_seniority == 1


def test_route_still_supports_monkeypatched_client(client, monkeypatch) -> None:
    """Existing tests patch src.routes.search.LinkedInClient; keep that working."""
    monkeypatch.setattr("src.routes.search.LinkedInClient", FakeClient, raising=True)
    response = client.post(
        "/search/fetch",
        json={
            "position_text": "ML engineer",
            "seniority": "Senior",
            "query_text": "Senior ML Engineer",
            "detail_delay_seconds": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["new_jobs"] == 1
    assert runner_module  # keep import used if refactored
