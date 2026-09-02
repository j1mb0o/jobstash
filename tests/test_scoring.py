import pytest

from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services.scoring import (
    add_cv_match_scores,
    add_final_scores,
    add_seniority_match_scores,
    calculate_final_score,
    calculate_seniority_match_score,
)


def record_with_levels(target: Seniority, returned: str | None) -> JobRecord:
    criteria = {} if returned is None else {"Seniority level": returned}
    return JobRecord(
        job_id="4123456789",
        title="Machine Learning Engineer",
        company="Example Co",
        location="Amsterdam",
        url="https://www.linkedin.com/jobs/view/4123456789",
        search_query="Senior ML Engineer",
        seniority=target,
        seniority_match_score=None,
        details=JobDetails(description="Build ML systems.", criteria=criteria),
    )


@pytest.mark.parametrize(
    ("target", "returned", "expected_score"),
    [
        (Seniority.intern, "Internship", 100),
        (Seniority.junior, "Entry level", 100),
        (Seniority.mid, "Associate", 100),
        (Seniority.senior, "Mid-Senior level", 100),
        (Seniority.lead, "Director", 100),
        (Seniority.principal, "Executive", 100),
        (Seniority.senior, "Associate", 88),
        (Seniority.senior, "Entry level", 61),
        (Seniority.senior, "Internship", 32),
    ],
)
def test_calculate_seniority_match_score_applies_distance(
    target: Seniority, returned: str, expected_score: int
) -> None:
    assert (
        calculate_seniority_match_score(record_with_levels(target, returned))
        == expected_score
    )


def test_seniority_match_score_is_symmetric_around_target() -> None:
    below_target = record_with_levels(Seniority.mid, "Entry level")
    above_target = record_with_levels(Seniority.mid, "Mid-Senior level")

    assert (
        calculate_seniority_match_score(below_target)
        == calculate_seniority_match_score(above_target)
        == 88
    )


def test_seniority_match_score_normalizes_returned_label() -> None:
    record = record_with_levels(Seniority.senior, "  MID-SENIOR LEVEL  ")

    assert calculate_seniority_match_score(record) == 100


@pytest.mark.parametrize(
    ("target", "returned"),
    [
        (Seniority.any, "Mid-Senior level"),
        (Seniority.senior, None),
        (Seniority.senior, "Unrecognized"),
    ],
)
def test_seniority_match_score_is_neutral_without_comparable_levels(
    target: Seniority, returned: str | None
) -> None:
    assert calculate_seniority_match_score(record_with_levels(target, returned)) == 100


def test_seniority_match_score_slightly_penalizes_not_applicable() -> None:
    record = record_with_levels(Seniority.senior, "Not Applicable")

    assert calculate_seniority_match_score(record) == 88


def test_add_seniority_match_scores_returns_scored_copies() -> None:
    record = record_with_levels(Seniority.senior, "Entry level")

    scored_records = add_seniority_match_scores([record])

    assert scored_records[0].seniority_match_score == 61
    assert record.seniority_match_score is None


class StubCVClient:
    def __init__(self, results: dict[str, float | None]) -> None:
        self.results = results
        self.calls: list[tuple[str, str]] = []

    def score_cv_match(self, record: JobRecord, cv_text: str) -> float | None:
        self.calls.append((record.job_id, cv_text))
        return self.results[record.job_id]


def test_calculate_final_score_multiplies_components() -> None:
    assert calculate_final_score(88, 0.5) == 44
    assert calculate_final_score(61, 0.9) == 55


def test_calculate_final_score_degrades_without_cv_score() -> None:
    assert calculate_final_score(88, None) == 88
    assert calculate_final_score(None, 0.5) is None
    assert calculate_final_score(None, None) is None


def test_add_cv_match_scores_attaches_client_scores() -> None:
    record = record_with_levels(Seniority.senior, "Entry level")
    client = StubCVClient({"4123456789": 0.4})

    scored_records = add_cv_match_scores([record], client, "my cv")

    assert scored_records[0].cv_match_score == 0.4
    assert record.cv_match_score is None
    assert client.calls == [("4123456789", "my cv")]


def test_add_cv_match_scores_keeps_none_when_client_cannot_score() -> None:
    record = record_with_levels(Seniority.senior, "Entry level")
    client = StubCVClient({"4123456789": None})

    scored_records = add_cv_match_scores([record], client, "my cv")

    assert scored_records[0].cv_match_score is None


def test_add_cv_match_scores_skips_records_without_description() -> None:
    record = record_with_levels(Seniority.senior, "Entry level").model_copy(
        update={"details": JobDetails(criteria={"Seniority level": "Entry level"})}
    )
    client = StubCVClient({})

    scored_records = add_cv_match_scores([record], client, "my cv")

    assert scored_records[0].cv_match_score is None
    assert client.calls == []


def test_add_final_scores_combines_score_components() -> None:
    record = add_seniority_match_scores(
        [record_with_levels(Seniority.senior, "Entry level")]
    )[0].model_copy(update={"cv_match_score": 0.9})

    finalized_records = add_final_scores([record])

    assert finalized_records[0].final_score == 55
    assert record.final_score is None


def test_add_final_scores_falls_back_to_seniority_score() -> None:
    record = add_seniority_match_scores(
        [record_with_levels(Seniority.senior, "Entry level")]
    )[0]

    finalized_records = add_final_scores([record])

    assert finalized_records[0].final_score == 61
