from pathlib import Path

import pytest

from src.schemas.search_config import SearchConfig
from src.services.search_configs import (
    SearchConfigError,
    list_config_files,
    list_config_names,
    load_config_by_name,
    load_config_file,
    save_config,
    slugify_name,
)


def test_slugify_name() -> None:
    assert slugify_name("ML NL Junior") == "ml-nl-junior"
    assert slugify_name("  Data_Scientist!! ") == "data-scientist"
    with pytest.raises(SearchConfigError):
        slugify_name("!!!   ")


def test_save_load_round_trip(tmp_path: Path) -> None:
    config = SearchConfig(
        name="ml-nl-junior",
        position_text="ML Engineer",
        location="Netherlands",
        max_pages=2,
    )
    path = save_config(tmp_path, config)
    assert path.is_file()
    assert path.name == "ml-nl-junior.json"

    loaded = load_config_file(path)
    assert loaded == config
    assert load_config_by_name(tmp_path, "ml-nl-junior") == config


def test_save_overwrites_same_slug(tmp_path: Path) -> None:
    save_config(tmp_path, SearchConfig(name="My Search", position_text="a"))
    save_config(tmp_path, SearchConfig(name="my search", position_text="b"))
    assert list_config_names(tmp_path) == ["my search"]
    assert load_config_by_name(tmp_path, "My Search").position_text == "b"


def test_list_skips_examples_and_corrupt_files(tmp_path: Path) -> None:
    save_config(tmp_path, SearchConfig(name="b-search"))
    save_config(tmp_path, SearchConfig(name="a-search"))
    (tmp_path / "notes.example.json").write_text('{"name": "x"}', encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "invalid.json").write_text('{"name": ""}', encoding="utf-8")

    assert list_config_names(tmp_path) == ["a-search", "b-search"]
    assert {p.name for p in list_config_files(tmp_path)} >= {
        "a-search.json",
        "b-search.json",
        "broken.json",
        "invalid.json",
    }
    assert all(
        not p.name.endswith(".example.json") for p in list_config_files(tmp_path)
    )


def test_load_missing_and_invalid_raise(tmp_path: Path) -> None:
    with pytest.raises(SearchConfigError):
        load_config_by_name(tmp_path, "nope")
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(SearchConfigError):
        load_config_file(bad)


def test_config_to_fetch_params() -> None:
    config = SearchConfig(name="x", position_text="ML", seniority="Senior")
    params = config.to_fetch_params()
    assert params.position_text == "ML"
    assert params.seniority.value == "Senior"


def test_find_config_file_matches_stem_or_internal_name(tmp_path: Path) -> None:
    from src.services.search_configs import find_config_file

    path = tmp_path / "my file.json"
    path.write_text(
        '{"name": "internal-name", "position_text": "ML"}', encoding="utf-8"
    )
    assert find_config_file(tmp_path, "my file") == path
    assert find_config_file(tmp_path, "my-file") == path
    assert find_config_file(tmp_path, "internal-name") == path
    with pytest.raises(SearchConfigError):
        find_config_file(tmp_path, "nope")


def test_find_config_file_accepts_path(tmp_path: Path, monkeypatch) -> None:
    from src.services.search_configs import find_config_file

    target = tmp_path / "elsewhere" / "custom.json"
    target.parent.mkdir()
    target.write_text('{"name": "custom", "position_text": "ML"}', encoding="utf-8")

    # Absolute path.
    assert find_config_file(tmp_path, str(target)) == target
    # Relative path with directory prefix (tab-completion style).
    monkeypatch.chdir(tmp_path)
    assert find_config_file(tmp_path / "configs", "elsewhere/custom.json") == (
        tmp_path / "elsewhere/custom.json"
    )
    with pytest.raises(SearchConfigError):
        find_config_file(tmp_path, "elsewhere/missing.json")
