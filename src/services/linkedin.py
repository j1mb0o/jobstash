import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from src.schemas.search import (
    JobDetails,
    JobRecord,
    JobSummary,
    SearchFilters,
    Seniority,
)
from src.services.scoring import title_within_seniority_tolerance

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JOB_POSTING_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """Records fetched from LinkedIn and cards dropped as already known.

    ``skipped_known`` counts unique cards whose job ID was in
    ``skip_job_ids``; no detail request was made for them.
    ``discarded_title`` counts unique cards dropped by the title
    seniority pre-filter; no detail request was made for them either.
    """

    records: list[JobRecord]
    skipped_known: int
    discarded_title: int = 0


class LinkedInClient:
    def __init__(
        self,
        timeout_seconds: float = 20.0,
        detail_delay_seconds: float = 1.5,
        max_retries: int = 3,
        retry_backoff_seconds: float = 8.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        if detail_delay_seconds < 0:
            raise ValueError("detail_delay_seconds cannot be negative.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative.")

        self.detail_delay_seconds = detail_delay_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def close(self) -> None:
        self._client.close()

    def search(
        self,
        queries: Iterable[str],
        filters: SearchFilters,
        seniority: Seniority,
        requested_positions: str,
        max_pages_per_query: int = 1,
        include_details: bool = True,
        status: str = "New",
        skip_job_ids: Iterable[str] = (),
    ) -> SearchResult:
        """Search across queries, skipping job IDs the caller already has.

        Cards whose job ID is in ``skip_job_ids`` are dropped before any
        detail request is made, so re-fetching known jobs costs only the
        search-page requests. Cards whose title already signals a
        seniority outside tolerance are likewise dropped before any
        detail request, so e.g. a ``Staff`` title never costs a detail
        fetch for a junior search. Cards are deduplicated by job ID across
        queries and pages.
        """
        if max_pages_per_query < 1:
            raise ValueError("max_pages_per_query must be at least one.")

        skip_ids = set(skip_job_ids)
        seen: set[str] = set()
        records: list[JobRecord] = []
        skipped_known = 0
        discarded_title = 0
        for query in queries:
            for page in range(max_pages_per_query):
                summaries = self.search_page(
                    query=query, filters=filters, start=page * 25
                )
                if not summaries:
                    break
                for summary in summaries:
                    if summary.job_id in seen:
                        continue
                    seen.add(summary.job_id)
                    if summary.job_id in skip_ids:
                        skipped_known += 1
                        continue
                    if not title_within_seniority_tolerance(summary.title, seniority):
                        discarded_title += 1
                        logger.info(
                            "Discarded job by title seniority mismatch "
                            "(target=%s): %s (%s)",
                            seniority.value,
                            summary.title,
                            summary.job_id,
                        )
                        continue
                    details = JobDetails()
                    if include_details:
                        details = self.fetch_details_or_empty(summary.job_id)
                        time.sleep(self.detail_delay_seconds)
                    records.append(
                        JobRecord(
                            **summary.model_dump(),
                            seniority=seniority,
                            requested_positions=requested_positions,
                            status=status,
                            details=details,
                        )
                    )
        if skipped_known:
            logger.info(
                "Skipped %s job cards already stored with descriptions.",
                skipped_known,
            )
        if discarded_title:
            logger.info(
                "Discarded %s job cards by title seniority mismatch.",
                discarded_title,
            )
        return SearchResult(
            records=records,
            skipped_known=skipped_known,
            discarded_title=discarded_title,
        )

    def search_page(
        self, query: str, filters: SearchFilters, start: int = 0
    ) -> list[JobSummary]:
        response = self._client.get(SEARCH_URL, params=filters.to_params(query, start))
        response.raise_for_status()
        return parse_search_results(response.text, query)

    def fetch_details_or_empty(self, job_id: str) -> JobDetails:
        try:
            return self.fetch_details(job_id)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Skipping details for job_id=%s after HTTP %s from LinkedIn.",
                job_id,
                exc.response.status_code,
            )
            return JobDetails()
        except httpx.HTTPError:
            logger.exception(
                "Skipping details for job_id=%s after LinkedIn request failure.",
                job_id,
            )
            return JobDetails()

    def fetch_details(self, job_id: str) -> JobDetails:
        url = JOB_POSTING_URL.format(job_id=job_id)
        attempt = 0
        while True:
            response = self._client.get(url)
            if response.status_code != 429:
                response.raise_for_status()
                return parse_job_details(response.text)

            if attempt >= self.max_retries:
                response.raise_for_status()

            wait_seconds = retry_after_seconds(
                response
            ) or self.retry_backoff_seconds * (attempt + 1)
            logger.warning(
                "LinkedIn returned 429 for job_id=%s. Retrying in %.1fs (attempt %s/%s).",
                job_id,
                wait_seconds,
                attempt + 1,
                self.max_retries,
            )
            time.sleep(wait_seconds)
            attempt += 1


def retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def parse_search_results(html: str, search_query: str) -> list[JobSummary]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li > div.base-card")
    jobs: list[JobSummary] = []
    for card in cards:
        title = text_or_empty(card.select_one("[class*=_title]"))
        company = text_or_empty(card.select_one("[class*=_subtitle]"))
        location = text_or_empty(card.select_one("[class*=_location]"))
        post_time = text_or_empty(card.select_one("[class*=listdate]"))
        link = card.select_one("[class*=_full-link]")
        if not isinstance(link, Tag):
            continue
        url = str(link.get("href", "")).strip()
        job_id = extract_job_id(url)
        if not job_id or not title:
            continue
        jobs.append(
            JobSummary(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                post_time=post_time,
                url=url,
                search_query=search_query,
            )
        )
    return jobs


def parse_job_details(html: str) -> JobDetails:
    soup = BeautifulSoup(html, "html.parser")
    description_node = soup.select_one("[class*=description] > section > div")
    criteria_node = soup.select_one("[class*=_job-criteria-list]")
    return JobDetails(
        description=text_or_empty(description_node, separator="\n"),
        criteria=parse_criteria(criteria_node),
    )


def parse_criteria(criteria_node: Tag | None) -> dict[str, str]:
    if criteria_node is None:
        return {}
    criteria: dict[str, str] = {}
    for item in criteria_node.select("li"):
        label = text_or_empty(item.select_one("h3"))
        value = text_or_empty(item.select_one("span"))
        if label and value:
            criteria[label] = value
    return criteria


def extract_job_id(url: str) -> str:
    query_params = parse_qs(urlparse(url).query)
    for key in ("currentJobId", "jobId"):
        for value in query_params.get(key, []):
            if value.isdigit():
                return value

    partial = url.split("?", maxsplit=1)[0].rstrip("/")
    if not partial:
        return ""
    last_segment = partial.rsplit("/", maxsplit=1)[-1]
    candidate = last_segment.rsplit("-", maxsplit=1)[-1]
    if candidate.isdigit():
        return candidate
    match = re.search(r"(\d{6,})", partial)
    return match.group(1) if match else ""


def text_or_empty(node: Tag | None, separator: str = " ") -> str:
    if node is None:
        return ""
    return " ".join(node.get_text(separator=separator, strip=True).split())
