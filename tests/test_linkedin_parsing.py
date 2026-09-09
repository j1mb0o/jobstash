from typing import Any

import httpx
import pytest

from src.schemas.search import JobDetails, JobSummary, SearchFilters, Seniority
from src.services import linkedin
from src.services.linkedin import (
    LinkedInClient,
    extract_job_id,
    parse_job_details,
    parse_search_results,
    retry_after_seconds,
)

SEARCH_HTML = """
<ul>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/ml-engineer-4123456789?ref=abc"></a>
      <h3 class="base-search-card__title"> ML Engineer </h3>
      <h4 class="base-search-card__subtitle"> Example Co </h4>
      <span class="job-search-card__location"> Amsterdam, Netherlands </span>
      <time class="job-search-card__listdate"> 1 day ago </time>
    </div>
  </li>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/data-scientist-5123456789"></a>
      <h3 class="base-search-card__title">Data
        Scientist</h3>
      <h4 class="base-search-card__subtitle"> Example Labs </h4>
      <span class="job-search-card__location"> Rotterdam </span>
    </div>
  </li>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/no-id"></a>
      <h3 class="base-search-card__title">Missing ID</h3>
    </div>
  </li>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/6123456789"></a>
    </div>
  </li>
</ul>
"""


DETAILS_HTML = """
<section class="show-more-less-html__markup">
  <div class="description__text description__text--rich">
    <section>
      <div>
        Build ML systems.

        Work with product teams.
      </div>
    </section>
  </div>
</section>
<ul class="description__job-criteria-list">
  <li>
    <h3>Seniority level</h3>
    <span>Mid-Senior level</span>
  </li>
  <li>
    <h3>Employment type</h3>
    <span>Full-time</span>
  </li>
  <li>
    <h3>Ignored empty value</h3>
    <span></span>
  </li>
</ul>
"""


def response(
    status_code: int, body: str = "", headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code,
        text=body,
        headers=headers,
        request=httpx.Request("GET", "https://www.linkedin.com/test"),
    )


def test_parse_search_results_extracts_complete_cards_and_skips_unusable_cards() -> (
    None
):
    jobs = parse_search_results(SEARCH_HTML, "ML Engineer")

    assert [job.job_id for job in jobs] == ["4123456789", "5123456789"]
    assert jobs[0].title == "ML Engineer"
    assert jobs[0].company == "Example Co"
    assert jobs[0].location == "Amsterdam, Netherlands"
    assert jobs[0].post_time == "1 day ago"
    assert (
        str(jobs[0].url)
        == "https://www.linkedin.com/jobs/view/ml-engineer-4123456789?ref=abc"
    )
    assert jobs[0].search_query == "ML Engineer"
    assert jobs[1].title == "Data Scientist"
    assert jobs[1].post_time == ""


@pytest.mark.parametrize(
    ("url", "job_id"),
    [
        (
            "https://www.linkedin.com/jobs/view/senior-ml-engineer-at-example-4123456789?position=1",
            "4123456789",
        ),
        ("https://www.linkedin.com/jobs/view/4123456789/", "4123456789"),
        (
            "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=5123456789",
            "5123456789",
        ),
        ("https://www.linkedin.com/jobs/view/not-a-job", ""),
        ("", ""),
    ],
)
def test_extract_job_id_handles_linkedin_url_shapes(url: str, job_id: str) -> None:
    assert extract_job_id(url) == job_id


def test_parse_job_details_normalizes_description_and_criteria() -> None:
    details = parse_job_details(DETAILS_HTML)

    assert details.description == "Build ML systems. Work with product teams."
    assert details.criteria == {
        "Seniority level": "Mid-Senior level",
        "Employment type": "Full-time",
    }


def test_parse_job_details_returns_empty_values_when_markup_is_missing() -> None:
    assert parse_job_details("<html></html>") == JobDetails()


def test_retry_after_seconds_accepts_positive_numbers_only() -> None:
    assert retry_after_seconds(response(429, headers={"Retry-After": "1.25"})) == 1.25
    assert retry_after_seconds(response(429, headers={"Retry-After": "-4"})) == 0.0
    assert retry_after_seconds(response(429, headers={"Retry-After": "soon"})) is None
    assert retry_after_seconds(response(429)) is None


def test_search_page_sends_filter_params_and_parses_results() -> None:
    captured: dict[str, Any] = {}

    class FakeHttpClient:
        def get(self, url: str, params: dict[str, Any]) -> httpx.Response:
            captured["url"] = url
            captured["params"] = params
            return response(200, SEARCH_HTML)

    client = LinkedInClient()
    client._client = FakeHttpClient()

    jobs = client.search_page(
        query="ML Engineer",
        filters=SearchFilters(location="Netherlands", easy_apply=True),
        start=25,
    )

    assert captured == {
        "url": linkedin.SEARCH_URL,
        "params": {
            "keywords": "ML Engineer",
            "start": 25,
            "location": "Netherlands",
            "f_AL": "true",
        },
    }
    assert [job.job_id for job in jobs] == ["4123456789", "5123456789"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout_seconds": 0}, "timeout_seconds must be greater than zero."),
        ({"detail_delay_seconds": -0.1}, "detail_delay_seconds cannot be negative."),
        ({"max_retries": -1}, "max_retries cannot be negative."),
        ({"retry_backoff_seconds": -0.1}, "retry_backoff_seconds cannot be negative."),
    ],
)
def test_client_rejects_invalid_tuning_values(
    kwargs: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        LinkedInClient(**kwargs)


def test_search_rejects_page_counts_below_one() -> None:
    client = LinkedInClient()

    with pytest.raises(ValueError, match="max_pages_per_query must be at least one."):
        client.search(
            queries=["python"],
            filters=SearchFilters(),
            seniority=Seniority.any,
            requested_positions="Engineer",
            max_pages_per_query=0,
        )

    client.close()


def test_search_deduplicates_across_queries_and_pages_and_fetches_details(
    monkeypatch,
) -> None:
    client = LinkedInClient(detail_delay_seconds=1.5)
    pages_seen: list[tuple[str, int]] = []
    detail_ids: list[str] = []
    sleeps: list[float] = []

    def search_page(
        query: str, filters: SearchFilters, start: int = 0
    ) -> list[JobSummary]:
        pages_seen.append((query, start))
        summaries = {
            ("python", 0): [
                JobSummary(
                    job_id="1",
                    title="Python Engineer",
                    company="Example",
                    location="Amsterdam",
                    url="https://www.linkedin.com/jobs/view/1",
                    search_query=query,
                )
            ],
            ("python", 25): [
                JobSummary(
                    job_id="2",
                    title="Backend Engineer",
                    company="Example",
                    location="Remote",
                    url="https://www.linkedin.com/jobs/view/2",
                    search_query=query,
                )
            ],
            ("ml", 0): [
                JobSummary(
                    job_id="1",
                    title="Duplicate Python Engineer",
                    company="Example",
                    location="Amsterdam",
                    url="https://www.linkedin.com/jobs/view/1",
                    search_query=query,
                )
            ],
            ("ml", 25): [],
        }
        return summaries.get((query, start), [])

    def fetch_details(job_id: str) -> JobDetails:
        detail_ids.append(job_id)
        return JobDetails(description=f"description {job_id}")

    monkeypatch.setattr(client, "search_page", search_page)
    monkeypatch.setattr(client, "fetch_details_or_empty", fetch_details)
    monkeypatch.setattr(linkedin.time, "sleep", sleeps.append)

    outcome = client.search(
        queries=["python", "ml"],
        filters=SearchFilters(),
        seniority=Seniority.senior,
        requested_positions="Software Engineer",
        max_pages_per_query=2,
        include_details=True,
        status="Interested",
    )
    client.close()

    assert pages_seen == [("python", 0), ("python", 25), ("ml", 0), ("ml", 25)]
    records = outcome.records
    assert [record.job_id for record in records] == ["1", "2"]
    assert [record.details.description for record in records] == [
        "description 1",
        "description 2",
    ]
    assert detail_ids == ["1", "2"]
    assert sleeps == [1.5, 1.5]
    assert outcome.skipped_known == 0
    assert {record.seniority for record in records} == {Seniority.senior}
    assert {record.requested_positions for record in records} == {"Software Engineer"}
    assert {record.status for record in records} == {"Interested"}


def test_search_skips_detail_fetching_when_disabled(monkeypatch) -> None:
    client = LinkedInClient(detail_delay_seconds=2.0)
    monkeypatch.setattr(
        client,
        "search_page",
        lambda query, filters, start=0: [
            JobSummary(
                job_id="1",
                title="ML Engineer",
                company="Example",
                location="Amsterdam",
                url="https://www.linkedin.com/jobs/view/1",
                search_query=query,
            )
        ],
    )
    monkeypatch.setattr(
        client,
        "fetch_details_or_empty",
        lambda job_id: pytest.fail("details should not be fetched"),
    )
    monkeypatch.setattr(
        linkedin.time,
        "sleep",
        lambda seconds: pytest.fail("sleep should not be called"),
    )

    outcome = client.search(
        queries=["ML Engineer"],
        filters=SearchFilters(),
        seniority=Seniority.any,
        requested_positions="ML engineer",
        include_details=False,
    )
    client.close()

    assert len(outcome.records) == 1
    assert outcome.records[0].details == JobDetails()
    assert outcome.skipped_known == 0


def test_search_skips_known_job_ids_before_detail_fetching(monkeypatch) -> None:
    client = LinkedInClient(detail_delay_seconds=1.5)
    detail_ids: list[str] = []
    sleeps: list[float] = []

    def summary(job_id: str, query: str) -> JobSummary:
        return JobSummary(
            job_id=job_id,
            title=f"Engineer {job_id}",
            company="Example",
            location="Amsterdam",
            url=f"https://www.linkedin.com/jobs/view/{job_id}",
            search_query=query,
        )

    def search_page(
        query: str, filters: SearchFilters, start: int = 0
    ) -> list[JobSummary]:
        if query == "python":
            return [summary("1", query), summary("2", query)]
        return [summary("1", query)]

    def fetch_details(job_id: str) -> JobDetails:
        detail_ids.append(job_id)
        return JobDetails(description=f"description {job_id}")

    monkeypatch.setattr(client, "search_page", search_page)
    monkeypatch.setattr(client, "fetch_details_or_empty", fetch_details)
    monkeypatch.setattr(linkedin.time, "sleep", sleeps.append)

    outcome = client.search(
        queries=["python", "ml"],
        filters=SearchFilters(),
        seniority=Seniority.any,
        requested_positions="Engineer",
        include_details=True,
        skip_job_ids={"1"},
    )
    client.close()

    assert [record.job_id for record in outcome.records] == ["2"]
    assert [record.details.description for record in outcome.records] == [
        "description 2"
    ]
    assert outcome.skipped_known == 1
    assert detail_ids == ["2"]
    assert sleeps == [1.5]


def test_fetch_details_retries_429_then_parses_success(monkeypatch) -> None:
    calls: list[str] = []

    class FakeHttpClient:
        def __init__(self) -> None:
            self.responses = [
                response(429, headers={"Retry-After": "0.2"}),
                response(200, DETAILS_HTML),
            ]

        def get(self, url: str) -> httpx.Response:
            calls.append(url)
            return self.responses.pop(0)

    client = LinkedInClient(max_retries=2, retry_backoff_seconds=10.0)
    client._client = FakeHttpClient()
    sleeps: list[float] = []
    monkeypatch.setattr(linkedin.time, "sleep", sleeps.append)

    details = client.fetch_details("4123456789")

    assert calls == [
        linkedin.JOB_POSTING_URL.format(job_id="4123456789"),
        linkedin.JOB_POSTING_URL.format(job_id="4123456789"),
    ]
    assert sleeps == [0.2]
    assert details.criteria["Employment type"] == "Full-time"


def test_fetch_details_uses_backoff_and_raises_after_max_retries(monkeypatch) -> None:
    class FakeHttpClient:
        def get(self, url: str) -> httpx.Response:
            return response(429)

    client = LinkedInClient(max_retries=1, retry_backoff_seconds=3.0)
    client._client = FakeHttpClient()
    sleeps: list[float] = []
    monkeypatch.setattr(linkedin.time, "sleep", sleeps.append)

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_details("4123456789")

    assert sleeps == [3.0]


def test_fetch_details_or_empty_swallows_linkedin_request_failures(monkeypatch) -> None:
    client = LinkedInClient()
    monkeypatch.setattr(
        client,
        "fetch_details",
        lambda job_id: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    assert client.fetch_details_or_empty("4123456789") == JobDetails()
    client.close()


def test_search_discards_title_mismatch_before_detail_fetching(monkeypatch) -> None:
    client = LinkedInClient(detail_delay_seconds=1.5)
    detail_ids: list[str] = []
    sleeps: list[float] = []

    def search_page(
        query: str, filters: SearchFilters, start: int = 0
    ) -> list[JobSummary]:
        return [
            JobSummary(
                job_id="1",
                title="Junior ML Engineer",
                company="Example",
                location="Amsterdam",
                url="https://www.linkedin.com/jobs/view/1",
                search_query=query,
            ),
            JobSummary(
                job_id="2",
                title="Staff ML Engineer",
                company="Example",
                location="Amsterdam",
                url="https://www.linkedin.com/jobs/view/2",
                search_query=query,
            ),
            JobSummary(
                job_id="3",
                title="Senior ML Engineer",
                company="Example",
                location="Amsterdam",
                url="https://www.linkedin.com/jobs/view/3",
                search_query=query,
            ),
        ]

    def fetch_details(job_id: str) -> JobDetails:
        detail_ids.append(job_id)
        return JobDetails(description=f"description {job_id}")

    monkeypatch.setattr(client, "search_page", search_page)
    monkeypatch.setattr(client, "fetch_details_or_empty", fetch_details)
    monkeypatch.setattr(linkedin.time, "sleep", sleeps.append)

    outcome = client.search(
        queries=["ML Engineer"],
        filters=SearchFilters(),
        seniority=Seniority.junior,
        requested_positions="ML engineer",
        include_details=True,
    )
    client.close()

    assert [record.job_id for record in outcome.records] == ["1"]
    assert outcome.discarded_title == 2
    assert detail_ids == ["1"]
    assert sleeps == [1.5]


def test_search_title_prefilter_applies_without_details(monkeypatch) -> None:
    client = LinkedInClient()
    monkeypatch.setattr(
        client,
        "search_page",
        lambda query, filters, start=0: [
            JobSummary(
                job_id="9",
                title="Staff Engineer",
                company="Example",
                location="Amsterdam",
                url="https://www.linkedin.com/jobs/view/9",
                search_query=query,
            )
        ],
    )
    monkeypatch.setattr(
        client,
        "fetch_details_or_empty",
        lambda job_id: pytest.fail("details should not be fetched"),
    )

    outcome = client.search(
        queries=["Engineer"],
        filters=SearchFilters(),
        seniority=Seniority.junior,
        requested_positions="Engineer",
        include_details=False,
    )
    client.close()

    assert outcome.records == []
    assert outcome.discarded_title == 1
