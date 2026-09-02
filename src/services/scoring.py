from math import exp
from typing import Protocol

from src.schemas.search import JobRecord, Seniority

TARGET_LEVELS = {
    Seniority.intern: 0,
    Seniority.junior: 1,
    Seniority.mid: 2,
    Seniority.senior: 3,
    Seniority.staff: 4,
    Seniority.lead: 5,
    Seniority.manager: 5,
    Seniority.principal: 6,
}

RETURNED_LEVELS = {
    "internship": 0,
    "entry level": 1,
    "associate": 2,
    "mid-senior level": 3,
    "director": 5,
    "executive": 6,
}


class CVMatchClient(Protocol):
    """LLM client interface used to score a job record against a CV."""

    def score_cv_match(self, record: JobRecord, cv_text: str) -> float | None: ...


def calculate_seniority_match_score(record: JobRecord) -> int:
    target_level = TARGET_LEVELS.get(record.seniority)
    returned_seniority = (
        record.details.criteria.get("Seniority level", "").strip().casefold()
    )
    if target_level is None:
        return 100

    if returned_seniority == "not applicable":
        level_difference = 1
    else:
        returned_level = RETURNED_LEVELS.get(returned_seniority)
        if returned_level is None:
            return 100
        level_difference = returned_level - target_level

    sigma = 2
    return round(100 * exp(-(level_difference**2) / (2 * sigma**2)))


def add_seniority_match_scores(records: list[JobRecord]) -> list[JobRecord]:
    return [
        record.model_copy(
            update={"seniority_match_score": calculate_seniority_match_score(record)}
        )
        for record in records
    ]


def calculate_final_score(
    seniority_match_score: int | None, cv_match_score: float | None
) -> int | None:
    """Combine the 0-100 seniority match with the 0-1 CV match.

    A missing CV score is treated as neutral so ranking degrades gracefully
    when the LLM is unavailable.
    """
    if seniority_match_score is None:
        return None
    if cv_match_score is None:
        return seniority_match_score
    return round(seniority_match_score * cv_match_score)


def add_cv_match_scores(
    records: list[JobRecord], client: CVMatchClient, cv_text: str
) -> list[JobRecord]:
    """Attach a 0-1 CV-match score to each record.

    Records without a stored description are skipped because they carry too
    little signal for a meaningful match; jobs the client cannot score keep
    a ``None`` CV score.
    """
    scored_records: list[JobRecord] = []
    for record in records:
        cv_match_score: float | None = None
        if record.details.description.strip():
            cv_match_score = client.score_cv_match(record, cv_text)
        scored_records.append(
            record.model_copy(update={"cv_match_score": cv_match_score})
        )
    return scored_records


def add_final_scores(records: list[JobRecord]) -> list[JobRecord]:
    """Attach the combined final score to each record."""
    return [
        record.model_copy(
            update={
                "final_score": calculate_final_score(
                    record.seniority_match_score, record.cv_match_score
                )
            }
        )
        for record in records
    ]
