import pytest

from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services.scoring import (
    add_seniority_match_scores,
    calculate_seniority_match_score,
    filter_records_by_title,
    filter_records_within_seniority,
    record_title_within_seniority_tolerance,
    record_within_seniority_tolerance,
    title_levels,
    title_within_seniority_tolerance,
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


@pytest.mark.parametrize(
    ("target", "returned"),
    [
        (Seniority.junior, "Mid-Senior level"),
        (Seniority.junior, "Director"),
        (Seniority.junior, "Executive"),
        (Seniority.senior, "Internship"),
        (Seniority.senior, "Entry level"),
    ],
)
def test_seniority_filter_discards_records_beyond_tolerance(
    target: Seniority, returned: str
) -> None:
    assert not record_within_seniority_tolerance(record_with_levels(target, returned))


@pytest.mark.parametrize(
    ("target", "returned"),
    [
        (Seniority.junior, "Entry level"),
        (Seniority.junior, "Associate"),
        (Seniority.senior, "Mid-Senior level"),
        (Seniority.senior, "Associate"),
    ],
)
def test_seniority_filter_keeps_records_within_tolerance(
    target: Seniority, returned: str
) -> None:
    assert record_within_seniority_tolerance(record_with_levels(target, returned))


@pytest.mark.parametrize(
    ("target", "returned"),
    [
        (Seniority.any, "Mid-Senior level"),
        (Seniority.any, "Director"),
        (Seniority.senior, None),
        (Seniority.senior, "Unrecognized"),
        (Seniority.senior, "Not Applicable"),
    ],
)
def test_seniority_filter_keeps_records_without_comparable_levels(
    target: Seniority, returned: str | None
) -> None:
    assert record_within_seniority_tolerance(record_with_levels(target, returned))


def test_filter_records_within_seniority_splits_records() -> None:
    exact = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"job_id": "1"}
    )
    near = record_with_levels(Seniority.junior, "Associate").model_copy(
        update={"job_id": "2"}
    )
    far = record_with_levels(Seniority.junior, "Mid-Senior level").model_copy(
        update={"job_id": "3"}
    )

    kept, discarded = filter_records_within_seniority([exact, near, far])

    assert [record.job_id for record in kept] == ["1", "2"]
    assert [record.job_id for record in discarded] == ["3"]


def test_add_seniority_match_scores_returns_scored_copies() -> None:
    record = record_with_levels(Seniority.senior, "Entry level")

    scored_records = add_seniority_match_scores([record])

    assert scored_records[0].seniority_match_score == 61
    assert record.seniority_match_score is None


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Junior Machine Learning Engineer", [1]),
        ("Jr. ML Engineer", [1]),
        ("Entry Level Data Scientist", [1]),
        ("Senior Software Engineer", [3]),
        ("Sr Software Engineer", [3]),
        ("Sr. Backend Developer", [3]),
        ("Staff ML Engineer", [4]),
        ("Lead Data Scientist", [5]),
        ("Engineering Manager", [5]),
        ("Principal Engineer", [6]),
        ("Machine Learning Engineer", []),
        ("Software Engineer", []),
        ("Team Leader in Logistics", []),
    ],
)
def test_title_levels_extracts_seniority_signals(
    title: str, expected: list[int]
) -> None:
    assert title_levels(title) == expected


def test_title_levels_is_case_insensitive() -> None:
    assert title_levels("STAFF ENGINEER") == [4]
    assert title_levels("staff engineer") == [4]


def test_title_levels_finds_multiple_signals() -> None:
    assert title_levels("Junior/Senior Engineer") == [1, 3]


@pytest.mark.parametrize(
    "title",
    [
        "Senior Machine Learning Engineer",
        "Sr ML Engineer",
        "Staff Software Engineer",
        "Lead Data Scientist",
        "Engineering Manager",
        "Principal Engineer",
        "Director of Engineering",
    ],
)
def test_title_filter_discards_explicit_mismatch_for_junior_target(
    title: str,
) -> None:
    assert not title_within_seniority_tolerance(title, Seniority.junior)


@pytest.mark.parametrize(
    "title",
    [
        "Junior ML Engineer",
        "Entry Level Developer",
        "Mid-Level Engineer",
        "Associate Engineer",
        "Machine Learning Engineer",
        "Software Engineer",
        "Junior/Senior Engineer",
    ],
)
def test_title_filter_keeps_match_or_signalless_title_for_junior_target(
    title: str,
) -> None:
    assert title_within_seniority_tolerance(title, Seniority.junior)


def test_title_filter_discards_junior_title_for_senior_target() -> None:
    assert not title_within_seniority_tolerance(
        "Junior Software Engineer", Seniority.senior
    )


def test_title_filter_keeps_staff_title_for_senior_target() -> None:
    assert title_within_seniority_tolerance("Staff Software Engineer", Seniority.senior)


@pytest.mark.parametrize("seniority", list(Seniority))
def test_title_filter_keeps_signalless_title_for_any_target(
    seniority: Seniority,
) -> None:
    assert title_within_seniority_tolerance("Machine Learning Engineer", seniority)


def test_title_filter_keeps_everything_for_any_seniority() -> None:
    assert title_within_seniority_tolerance("Staff Engineer", Seniority.any)


def test_record_title_filter_uses_record_title_and_seniority() -> None:
    matching = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"title": "Junior Engineer"}
    )
    mismatching = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"title": "Staff Engineer"}
    )

    assert record_title_within_seniority_tolerance(matching)
    assert not record_title_within_seniority_tolerance(mismatching)


def test_filter_records_by_title_splits_records() -> None:
    junior_title = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"job_id": "1", "title": "Junior Engineer"}
    )
    plain_title = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"job_id": "2", "title": "Machine Learning Engineer"}
    )
    staff_title = record_with_levels(Seniority.junior, "Entry level").model_copy(
        update={"job_id": "3", "title": "Staff Engineer"}
    )

    kept, discarded = filter_records_by_title([junior_title, plain_title, staff_title])

    assert [record.job_id for record in kept] == ["1", "2"]
    assert [record.job_id for record in discarded] == ["3"]
