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
