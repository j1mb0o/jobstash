from src.schemas.search import Seniority
from src.services.query_generation import (
    dedupe,
    expand_position,
    generate_queries,
    resolve_queries,
    split_lines_or_commas,
)


def test_split_lines_or_commas_trims_entries_and_ignores_blanks() -> None:
    assert split_lines_or_commas(
        " ML engineer, Data Scientist \n\nData Engineer,, "
    ) == [
        "ML engineer",
        "Data Scientist",
        "Data Engineer",
    ]


def test_expand_position_uses_case_and_whitespace_insensitive_aliases() -> None:
    assert expand_position("  MACHINE   learning ENGINEER ") == [
        "Machine Learning Engineer",
        "ML Engineer",
        "Machine Learning Researcher",
        "ML Researcher",
        "Applied Machine Learning Engineer",
        "AI Engineer",
    ]


def test_expand_position_keeps_unknown_positions_trimmed() -> None:
    assert expand_position("  Prompt Engineer  ") == ["Prompt Engineer"]
    assert expand_position("   ") == []


def test_generate_queries_combines_aliases_with_seniority_prefixes_in_order() -> None:
    queries = generate_queries(["ML engineer"], Seniority.senior)

    assert queries[:6] == [
        "Senior Machine Learning Engineer",
        "Sr Machine Learning Engineer",
        "Senior ML Engineer",
        "Sr ML Engineer",
        "Senior Machine Learning Researcher",
        "Sr Machine Learning Researcher",
    ]
    assert len(queries) == 12
    assert len(queries) == len({query.casefold() for query in queries})


def test_generate_queries_with_any_seniority_does_not_prefix_aliases() -> None:
    assert generate_queries(["Data Scientist"], Seniority.any) == [
        "Data Scientist",
        "Machine Learning Scientist",
        "Applied Scientist",
        "Research Scientist",
    ]


def test_generate_queries_deduplicates_across_positions_case_insensitively() -> None:
    assert generate_queries(
        ["ML engineer", "machine learning engineer"], Seniority.intern
    ) == [
        "Intern Machine Learning Engineer",
        "Internship Machine Learning Engineer",
        "Intern ML Engineer",
        "Internship ML Engineer",
        "Intern Machine Learning Researcher",
        "Internship Machine Learning Researcher",
        "Intern ML Researcher",
        "Internship ML Researcher",
        "Intern Applied Machine Learning Engineer",
        "Internship Applied Machine Learning Engineer",
        "Intern AI Engineer",
        "Internship AI Engineer",
    ]


def test_dedupe_normalizes_whitespace_and_preserves_first_casing() -> None:
    assert dedupe(
        [" ML   Engineer ", "ml engineer", "Data Scientist", "", " data scientist "]
    ) == [
        "ML Engineer",
        "Data Scientist",
    ]


def test_resolve_queries_prefers_edited_query_text_over_generation() -> None:
    assert resolve_queries(
        "ML engineer", Seniority.senior, "Senior Python Engineer"
    ) == [
        "Senior Python Engineer",
    ]


def test_resolve_queries_falls_back_to_generated_queries() -> None:
    assert resolve_queries("Data Scientist", Seniority.any, "") == [
        "Data Scientist",
        "Machine Learning Scientist",
        "Applied Scientist",
        "Research Scientist",
    ]
