import json

import httpx
import pytest

from src.schemas.search import JobDetails, JobRecord
from src.services.openrouter import (
    LANGUAGE_MISMATCH_SCORE,
    OpenRouterClient,
    OpenRouterError,
    build_job_text,
    build_scoring_prompt,
    load_cv_text,
    parse_cv_score,
)


def make_record(description: str = "Build ML systems.") -> JobRecord:
    return JobRecord(
        job_id="4123456789",
        title="Machine Learning Engineer",
        company="Example Co",
        location="Amsterdam",
        url="https://www.linkedin.com/jobs/view/4123456789",
        search_query="ML Engineer",
        details=JobDetails(
            description=description,
            criteria={"Seniority level": "Mid-Senior level"},
        ),
    )


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "https://openrouter.ai/test"),
    )


def make_client(handler, max_retries: int = 0, **kwargs: object) -> OpenRouterClient:
    defaults: dict[str, object] = {
        "api_key": "test-key",
        "model": "test-model",
        "request_delay_seconds": 0,
        "retry_backoff_seconds": 0,
        "max_retries": max_retries,
    }
    defaults.update(kwargs)
    return OpenRouterClient(transport=httpx.MockTransport(handler), **defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"score": 0.7}', 0.7),
        ('```json\n{"score": 0.25}\n```', 0.25),
        ("0.9", 0.9),
        ("The score is 0.6", 0.6),
        ('{"score": 1.4}', 1.0),
        ("85% match", 0.85),
        ('{"score": -0.2}', 0.0),
    ],
)
def test_parse_cv_score_extracts_values(content: str, expected: float) -> None:
    assert parse_cv_score(content) == expected


def test_parse_cv_score_rejects_content_without_numbers() -> None:
    with pytest.raises(OpenRouterError):
        parse_cv_score("cannot parse this")


def test_build_job_text_includes_job_fields() -> None:
    text = build_job_text(make_record())

    assert "Title: Machine Learning Engineer" in text
    assert "Company: Example Co" in text
    assert "Experience level: Mid-Senior level" in text
    assert "Build ML systems." in text


def test_build_job_text_truncates_long_descriptions() -> None:
    record = make_record(description="x" * 500)

    text = build_job_text(record, max_chars=100)

    assert "[truncated]" in text
    assert "x" * 500 not in text


def test_build_scoring_prompt_sets_language_mismatch_rule() -> None:
    prompt = build_scoring_prompt(make_record(), "Languages: English, Greek")

    assert "Language rule" in prompt
    assert f'{{"score": {LANGUAGE_MISMATCH_SCORE}}}' in prompt
    assert "Languages: English, Greek" in prompt
    assert "nice to have" in prompt


def test_load_cv_text_reads_file(tmp_path) -> None:
    cv_file = tmp_path / "cv.md"
    cv_file.write_text("# My CV\n", encoding="utf-8")

    assert load_cv_text(str(cv_file)) == "# My CV"


def test_load_cv_text_returns_empty_for_missing_file(tmp_path) -> None:
    assert load_cv_text(str(tmp_path / "missing.md")) == ""


def test_score_cv_match_sends_model_and_parses_score() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return chat_response('{"score": 0.8}')

    client = make_client(handler)
    try:
        score = client.score_cv_match(make_record(), "my cv")
    finally:
        client.close()

    assert score == 0.8
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert body["model"] == "test-model"  # type: ignore[index]
    messages = body["messages"]  # type: ignore[index]
    assert messages[0]["role"] == "system"
    assert "my cv" in messages[1]["content"]


def test_score_cv_match_retries_transient_failures() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, request=request)
        return chat_response('{"score": 0.6}')

    client = make_client(handler, max_retries=1)
    try:
        assert client.score_cv_match(make_record(), "my cv") == 0.6
    finally:
        client.close()

    assert len(calls) == 2


def test_score_cv_match_returns_none_after_exhausted_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = make_client(handler, max_retries=1)
    try:
        assert client.score_cv_match(make_record(), "my cv") is None
    finally:
        client.close()


def test_score_cv_match_fails_fast_on_client_errors() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(401, request=request)

    client = make_client(handler, max_retries=2)
    try:
        assert client.score_cv_match(make_record(), "my cv") is None
    finally:
        client.close()

    assert len(calls) == 1


def test_score_cv_match_returns_none_on_unparseable_content() -> None:
    client = make_client(lambda request: chat_response("no numbers here"))
    try:
        assert client.score_cv_match(make_record(), "my cv") is None
    finally:
        client.close()
