import pytest

from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services.scoring import (
    add_seniority_match_scores,
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
        details=JobDetails(criteria=criteria),
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
