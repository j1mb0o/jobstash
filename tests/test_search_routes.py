from typing import Any

from fastapi.testclient import TestClient

from src.models.job import Job
from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services import linkedin as linkedin_module
from src.services.linkedin import SearchResult


class FakeLinkedInClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.detail_delay_seconds = kwargs.get("detail_delay_seconds", 0)

    def search(self, **kwargs: Any) -> SearchResult:
        seniority = kwargs.get("seniority", Seniority.any)
        skip_ids = set(kwargs.get("skip_job_ids", ()))
        all_records = [
            JobRecord(
                job_id="4123456789",
                title="Machine Learning Engineer",
                company="Example Co",
                location="Amsterdam, Netherlands",
                post_time="1 day ago",
                url="https://www.linkedin.com/jobs/view/4123456789",
                search_query=kwargs.get("queries", ["Senior ML Engineer"])[0],
                seniority=seniority,
                requested_positions=kwargs.get("requested_positions", "ML engineer"),
                status="New",
                details=JobDetails(
                    description="Build ML systems.",
                    criteria={"Seniority level": "Mid-Senior level"},
                ),
            )
        ]
        records = [record for record in all_records if record.job_id not in skip_ids]
        return SearchResult(
            records=records,
            skipped_known=len(all_records) - len(records),
        )

    def close(self) -> None:
        pass


def test_search_page_renders_form_and_choices(client: TestClient) -> None:
    response = client.get("/search")

    assert response.status_code == 200
    assert "Search queries" in response.text
    assert "Generate queries" in response.text
    assert "Fetch now" in response.text
    assert "Netherlands" in response.text
    assert 'value="Junior" selected' in response.text
    assert "Any" in response.text


def test_search_page_places_any_seniority_last(client: TestClient) -> None:
    response = client.get("/search")
    text = response.text
    any_pos = text.find('value="Any"')
    junior_pos = text.find('value="Junior"')

    assert any_pos > junior_pos


def test_generate_queries_endpoint_returns_queries(client: TestClient) -> None:
    response = client.post(
        "/search/queries",
        json={"position_text": "ML engineer", "seniority": "Senior"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "queries": [
            "Senior Machine Learning Engineer",
            "Sr Machine Learning Engineer",
            "Senior ML Engineer",
            "Sr ML Engineer",
            "Senior Machine Learning Researcher",
            "Sr Machine Learning Researcher",
            "Senior ML Researcher",
            "Sr ML Researcher",
            "Senior Applied Machine Learning Engineer",
            "Sr Applied Machine Learning Engineer",
            "Senior AI Engineer",
            "Sr AI Engineer",
        ]
    }


def test_generate_queries_with_empty_positions_returns_nothing(
    client: TestClient,
) -> None:
    response = client.post(
        "/search/queries",
        json={"position_text": "  ,  ", "seniority": "Any"},
    )

    assert response.status_code == 200
    assert response.json() == {"queries": []}


def test_fetch_jobs_persists_results_and_returns_summary(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(linkedin_module, "time", linkedin_module.time)
    monkeypatch.setattr(
        "src.routes.search.LinkedInClient", FakeLinkedInClient, raising=True
    )

    response = client.post(
        "/search/fetch",
        json={
            "position_text": "ML engineer",
            "seniority": "Senior",
            "query_text": "Senior ML Engineer",
            "location": "Netherlands",
            "max_pages": 1,
            "include_details": True,
            "detail_delay_seconds": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_jobs"] == 1
    assert payload["queries"] == ["Senior ML Engineer"]

    api_response = client.get("/api/jobs")
    assert api_response.status_code == 200
    job = api_response.json()[0]
    assert job["title"] == "Machine Learning Engineer"


def test_fetch_jobs_skips_stored_jobs_before_saving(
    client: TestClient, monkeypatch, add_job
) -> None:
    add_job(
        linkedin_job_id="4123456789",
        title="Machine Learning Engineer",
        description="Stored full description.",
    )

    def record(job_id: str, title: str) -> JobRecord:
        return JobRecord(
            job_id=job_id,
            title=title,
            company="Example Co",
            location="Amsterdam, Netherlands",
            post_time="1 day ago",
            url=f"https://www.linkedin.com/jobs/view/{job_id}",
            search_query="Senior ML Engineer",
            seniority=Seniority.senior,
            requested_positions="ML engineer",
            status="New",
            details=JobDetails(
                description="Build ML systems.",
                criteria={"Seniority level": "Mid-Senior level"},
            ),
        )

    class TwoJobClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.detail_delay_seconds = kwargs.get("detail_delay_seconds", 0)

        def search(self, **kwargs: Any) -> SearchResult:
            skip_ids = set(kwargs.get("skip_job_ids", ()))
            all_records = [
                record("4123456789", "Machine Learning Engineer"),
                record("9999999999", "Data Scientist"),
            ]
            kept = [r for r in all_records if r.job_id not in skip_ids]
            return SearchResult(
                records=kept,
                skipped_known=len(all_records) - len(kept),
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr("src.routes.search.LinkedInClient", TwoJobClient, raising=True)

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
    payload = response.json()
    assert payload["new_jobs"] == 1
    assert payload["already_stored"] == 1
    assert payload["skipped"] == 0

    session_factory = client.app.state.session_factory
    with session_factory() as session:
        stored = {
            job.linkedin_job_id: job
            for job in session.query(Job).filter(Job.linkedin_job_id.is_not(None))
        }

    known = stored["4123456789"]
    assert known.description == "Stored full description."
    assert stored["9999999999"].seniority_match_score is not None


def test_fetch_jobs_discards_senior_job_against_junior_target(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.routes.search.LinkedInClient", FakeLinkedInClient, raising=True
    )

    response = client.post(
        "/search/fetch",
        json={
            "position_text": "ML engineer",
            "seniority": "Junior",
            "query_text": "Junior ML Engineer",
            "detail_delay_seconds": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_jobs"] == 0
    assert payload["discarded_seniority"] == 1
    assert "1 discarded (experience mismatch)" in payload["message"]

    assert client.get("/api/jobs").json() == []


def test_fetch_jobs_without_queries_returns_400(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.routes.search.LinkedInClient", FakeLinkedInClient, raising=True
    )

    response = client.post(
        "/search/fetch",
        json={"position_text": "  ", "seniority": "Any", "query_text": ""},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Add at least one position or query."}


def test_fetch_jobs_translates_linkedin_http_error_to_502(
    client: TestClient, monkeypatch
) -> None:
    class ErrorClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.detail_delay_seconds = 0

        def search(self, **kwargs: Any) -> list[JobRecord]:
            import httpx

            raise httpx.HTTPStatusError(
                "Forbidden",
                request=httpx.Request("GET", "https://linkedin.com"),
                response=httpx.Response(403),
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr("src.routes.search.LinkedInClient", ErrorClient, raising=True)

    response = client.post(
        "/search/fetch",
        json={"position_text": "ML engineer", "seniority": "Any"},
    )

    assert response.status_code == 502
    assert "403" in response.json()["detail"]
