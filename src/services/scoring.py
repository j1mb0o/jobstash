from math import exp

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

SENIORITY_FILTER_TOLERANCE = 1
"""Maximum level distance between requested and returned seniority.

Records whose returned ``Seniority level`` is further away than this
are discarded after the detail fetch, before scoring and storage.
"""


def record_within_seniority_tolerance(record: JobRecord) -> bool:
    """Whether the record's returned seniority is close enough to keep.

    Records without a comparable level are always kept: the requested
    seniority is ``Any``, the criteria are missing (details were not
    fetched), or the returned level is unrecognized or ``Not
    applicable``.
    """
    target_level = TARGET_LEVELS.get(record.seniority)
    if target_level is None:
        return True
    returned_seniority = (
        record.details.criteria.get("Seniority level", "").strip().casefold()
    )
    returned_level = RETURNED_LEVELS.get(returned_seniority)
    if returned_level is None:
        return True
    return abs(returned_level - target_level) <= SENIORITY_FILTER_TOLERANCE


def filter_records_within_seniority(
    records: list[JobRecord],
) -> tuple[list[JobRecord], list[JobRecord]]:
    """Split records into kept and discarded by seniority tolerance.

    Discarded records carry a returned ``Seniority level`` more than
    :data:`SENIORITY_FILTER_TOLERANCE` levels away from the requested
    seniority; callers should drop them before scoring and storage.
    """
    kept: list[JobRecord] = []
    discarded: list[JobRecord] = []
    for record in records:
        if record_within_seniority_tolerance(record):
            kept.append(record)
        else:
            discarded.append(record)
    return kept, discarded


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
