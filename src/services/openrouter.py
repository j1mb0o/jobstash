import json
import logging
import re
import time
from pathlib import Path

import httpx

from src.schemas.search import JobRecord

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_DESCRIPTION_CHARS = 6000
LANGUAGE_MISMATCH_SCORE = 0.45

SYSTEM_PROMPT = (
    "You are an expert technical recruiter who compares a candidate CV with "
    "a job posting and rates how well the candidate matches the job. "
    "Hard language requirements the candidate does not speak are a strong "
    "negative signal."
)


class OpenRouterError(Exception):
    """Raised when the OpenRouter API fails or returns an unusable response."""


class _RetryableError(Exception):
    """Internal marker for transient failures that are worth retrying."""


def load_cv_text(cv_path: str) -> str:
    """Return the CV file contents, or an empty string when unavailable."""
    try:
        return Path(cv_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Could not read CV file %s: %s", cv_path, exc)
        return ""


def build_job_text(record: JobRecord, max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """Build a compact text representation of a job for the scoring prompt."""
    description = record.details.description
    if len(description) > max_chars:
        description = f"{description[:max_chars]}\n[truncated]"
    lines = [
        f"Title: {record.title}",
        f"Company: {record.company}",
        f"Location: {record.location}",
    ]
    experience_level = record.details.criteria.get("Seniority level", "").strip()
    if experience_level:
        lines.append(f"Experience level: {experience_level}")
    lines.append(f"Description:\n{description}")
    return "\n".join(lines)


def build_scoring_prompt(record: JobRecord, cv_text: str) -> str:
    return (
        f"Candidate CV:\n{cv_text}\n\n"
        f"Job posting:\n{build_job_text(record)}\n\n"
        "Rate how well the candidate matches this job on a scale from 0.0 "
        "(no match) to 1.0 (excellent match). Consider required skills, "
        "experience level, domain, and responsibilities.\n"
        "Language rule: first check the job posting for required languages "
        '(phrases such as "fluent Dutch", "native German", "Dutch C1", or a '
        "language listed as required/mandatory). Compare them with the "
        "languages the candidate speaks according to the CV. If the job "
        "requires a language the candidate does not speak, respond with "
        f'exactly {{"score": {LANGUAGE_MISMATCH_SCORE}}} and no other text. '
        "Languages that are only a plus, preferred, or nice to have do not "
        "trigger this rule.\n"
        'Respond with only a JSON object such as {"score": 0.7} and no '
        "other text."
    )


def parse_cv_score(content: str) -> float:
    """Extract a score between 0.0 and 1.0 from a model response."""
    cleaned = re.sub(r"```(?:json)?", "", content).strip()
    value: float | None = None
    try:
        value = float(json.loads(cleaned)["score"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        score_match = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', cleaned)
        if score_match is None:
            score_match = re.search(r"([0-9]*\.?[0-9]+)", cleaned)
        if score_match is not None:
            value = float(score_match.group(1))
    if value is None:
        raise OpenRouterError("Model response contained no score.")
    if value > 1 and "%" in cleaned:
        value /= 100
    return min(1.0, max(0.0, value))


class OpenRouterClient:
    """Minimal OpenRouter client that scores job records against a CV."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_backoff_seconds: float = 2.0,
        request_delay_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative.")
        if request_delay_seconds < 0:
            raise ValueError("request_delay_seconds cannot be negative.")

        self.model = model
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.request_delay_seconds = request_delay_seconds
        self._last_request_at: float | None = None
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def score_cv_match(self, record: JobRecord, cv_text: str) -> float | None:
        """Return a 0-1 match score for one job record against the CV text.

        Returns ``None`` when the API fails or the response cannot be parsed,
        so a single bad job never breaks the whole fetch.
        """
        prompt = build_scoring_prompt(record, cv_text)
        for attempt in range(self.max_retries + 1):
            self._wait_for_request_slot()
            try:
                return self._request_score(prompt)
            except _RetryableError as exc:
                if attempt >= self.max_retries:
                    logger.warning(
                        "OpenRouter scoring gave up on %s after %s attempts: %s",
                        record.title,
                        attempt + 1,
                        exc,
                    )
                    return None
                backoff = self.retry_backoff_seconds * (attempt + 1)
                logger.warning(
                    "OpenRouter scoring attempt %s failed (%s); retrying in %ss.",
                    attempt + 1,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
            except OpenRouterError as exc:
                logger.warning(
                    "OpenRouter scoring failed for %s: %s", record.title, exc
                )
                return None
        return None

    def _wait_for_request_slot(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.request_delay_seconds - (
            time.monotonic() - self._last_request_at
        )
        if remaining > 0:
            time.sleep(remaining)

    def _request_score(self, prompt: str) -> float:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 512,
        }
        self._last_request_at = time.monotonic()
        try:
            response = self._client.post(OPENROUTER_CHAT_URL, json=payload)
        except httpx.HTTPError as exc:
            raise _RetryableError(f"request error: {exc}") from exc
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise _RetryableError(f"HTTP {response.status_code}")
        if response.is_error:
            raise OpenRouterError(f"OpenRouter returned HTTP {response.status_code}.")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OpenRouterError(
                "OpenRouter response was missing chat content."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("OpenRouter returned empty chat content.")
        try:
            return parse_cv_score(content)
        except OpenRouterError as exc:
            raise OpenRouterError(f"Unusable model response: {exc}") from exc
