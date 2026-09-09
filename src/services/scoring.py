import re
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

TITLE_LEVEL_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), level)
    for pattern, level in [
        (r"\bintern(?:ship|s)?\b", 0),
        (r"\bjunior\b", 1),
        (r"\bjr\.?\b", 1),
        (r"\bentry\b", 1),
        (r"\bgraduate\b", 1),
        (r"\btrainee\b", 1),
        (r"\bapprentice\b", 1),
        (r"\bworking[\s-]+student\b", 1),
        (r"\bmid\b", 2),
        (r"\bmid[\s-]*level\b", 2),
        (r"\bintermediate\b", 2),
        (r"\bassociate\b", 2),
        (r"\bsenior\b", 3),
        (r"\bsr\.?\b", 3),
        (r"\bstaff\b", 4),
        (r"\blead\b", 5),
        (r"\bteam[\s-]+lead\b", 5),
        (r"\bmanager\b", 5),
        (r"\bdirector\b", 5),
        (r"\bhead\b", 5),
        (r"\bprincipal\b", 6),
        (r"\bexecutive\b", 6),
        (r"\bvp\b", 6),
        (r"\bvice[\s-]+president\b", 6),
        (r"\bcto\b", 6),
        (r"\bchief\b", 6),
        (r"\bdistinguished\b", 6),
    ]
)
"""Title keywords mapped to the :data:`TARGET_LEVELS` scale.

Only explicit seniority signals are listed. Titles without any match
carry no signal and are always kept.
"""


def title_levels(title: str) -> list[int]:
    """Sorted seniority levels signaled by a job title."""
    return sorted(
        {level for pattern, level in TITLE_LEVEL_PATTERNS if pattern.search(title)}
    )


def title_within_seniority_tolerance(title: str, seniority: Seniority) -> bool:
    """Whether a job title is close enough to the requested seniority to keep.

    Titles without an explicit seniority signal are always kept. When a
    title carries several signals (e.g. ``Associate Director``), the title
    is kept when any signal is within
    :data:`SENIORITY_FILTER_TOLERANCE` of the target, so ambiguous titles
    are never discarded early.
    """
    target_level = TARGET_LEVELS.get(seniority)
    if target_level is None:
        return True
    levels = title_levels(title)
    if not levels:
        return True
    return any(
        abs(level - target_level) <= SENIORITY_FILTER_TOLERANCE for level in levels
    )


def record_title_within_seniority_tolerance(record: JobRecord) -> bool:
    """Whether the record's title is close enough to the requested seniority."""
    return title_within_seniority_tolerance(record.title, record.seniority)


def filter_records_by_title(
    records: list[JobRecord],
) -> tuple[list[JobRecord], list[JobRecord]]:
    """Split records into kept and discarded by title seniority signal.

    Discarded records carry an explicit title signal (e.g. ``Staff`` or
    ``Senior``) more than :data:`SENIORITY_FILTER_TOLERANCE` levels away
    from the requested seniority; callers should drop them before the
    detail fetch, scoring, and storage.
    """
    kept: list[JobRecord] = []
    discarded: list[JobRecord] = []
    for record in records:
        if record_title_within_seniority_tolerance(record):
            kept.append(record)
        else:
            discarded.append(record)
    return kept, discarded


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
