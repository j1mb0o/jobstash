from collections.abc import Iterable

from src.schemas.search import Seniority

POSITION_ALIASES: dict[str, list[str]] = {
    "ml engineer": [
        "Machine Learning Engineer",
        "ML Engineer",
        "Machine Learning Researcher",
        "ML Researcher",
        "Applied Machine Learning Engineer",
        "AI Engineer",
    ],
    "machine learning engineer": [
        "Machine Learning Engineer",
        "ML Engineer",
        "Machine Learning Researcher",
        "ML Researcher",
        "Applied Machine Learning Engineer",
        "AI Engineer",
    ],
    "data scientist": [
        "Data Scientist",
        "Machine Learning Scientist",
        "Applied Scientist",
        "Research Scientist",
    ],
    "data engineer": [
        "Data Engineer",
        "Analytics Engineer",
        "Big Data Engineer",
        "Platform Data Engineer",
    ],
    "software engineer": [
        "Software Engineer",
        "Backend Engineer",
        "Full Stack Engineer",
        "Software Developer",
    ],
}


def split_lines_or_commas(value: str) -> list[str]:
    parts: list[str] = []
    for line in value.splitlines():
        parts.extend(piece.strip() for piece in line.split(","))
    return [part for part in parts if part]


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def expand_position(position: str) -> list[str]:
    normalized = " ".join(position.lower().strip().split())
    aliases = POSITION_ALIASES.get(normalized, [position.strip()])
    return dedupe(aliases)


def generate_queries(positions: Iterable[str], seniority: Seniority) -> list[str]:
    queries: list[str] = []
    for position in positions:
        for alias in expand_position(position):
            for prefix in seniority.query_prefixes:
                query = f"{prefix} {alias}".strip()
                queries.append(query)
    return dedupe(queries)


def resolve_queries(
    position_text: str,
    seniority: Seniority,
    query_text: str,
) -> list[str]:
    """Prefer edited queries, fall back to generated ones from positions."""
    return split_lines_or_commas(query_text) or generate_queries(
        split_lines_or_commas(position_text), seniority
    )
