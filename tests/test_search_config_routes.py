from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings, get_settings


def make_client(tmp_path: Path, config_dir: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test-jobs.db'}",
        search_config_dir=str(config_dir),
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_config_api_save_load_list(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    with make_client(tmp_path, config_dir) as client:
        assert client.get("/api/search-configs").json() == {"configs": []}

        payload = {
            "name": "ml-nl-junior",
            "position_text": "ML Engineer",
            "seniority": "Junior",
            "location": "Netherlands",
            "max_pages": 2,
            "detail_delay_seconds": 0,
        }
        saved = client.post("/api/search-configs", json=payload)
        assert saved.status_code == 200
        assert saved.json()["name"] == "ml-nl-junior"
        assert (config_dir / "ml-nl-junior.json").is_file()

        listed = client.get("/api/search-configs")
        assert listed.json() == {"configs": ["ml-nl-junior"]}

        loaded = client.get("/api/search-configs/ml-nl-junior")
        assert loaded.status_code == 200
        assert loaded.json()["location"] == "Netherlands"


def test_config_api_unknown_returns_404(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    with make_client(tmp_path, config_dir) as client:
        response = client.get("/api/search-configs/nope")
        assert response.status_code == 404


def test_cli_discover_and_dry_run(tmp_path: Path, capsys) -> None:
    from scripts.fetch_jobs import discover_configs, main

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "b.json").write_text(
        '{"name": "b", "position_text": "ML", "seniority": "Junior"}',
        encoding="utf-8",
    )
    (config_dir / "a.json").write_text(
        '{"name": "a", "position_text": "Data", "seniority": "Junior"}',
        encoding="utf-8",
    )
    (config_dir / "skip.example.json").write_text('{"name": "x"}', encoding="utf-8")

    files = discover_configs(config_dir, [], True)
    assert [p.name for p in files] == ["a.json", "b.json"]

    code = main(["--all", "--config-dir", str(config_dir), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[a] would run" in out


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize(
    ("position_text", "query_text", "expected"),
    [
        ("ML Engineer", "", ["ML Engineer"]),
        (
            "ML Engineer, Data Scientist\nData Engineer",
            " , \n",
            ["ML Engineer", "Data Scientist", "Data Engineer"],
        ),
        (
            "ML Engineer",
            "Junior AI Engineer\nML Researcher",
            ["Junior AI Engineer", "ML Researcher"],
        ),
        (" , \n", "", []),
    ],
)
def test_cli_uses_literal_queries(
    tmp_path: Path, monkeypatch, capsys, dry_run, position_text, query_text, expected
) -> None:
    from scripts import fetch_jobs
    from src.schemas.search import Seniority
    from src.schemas.search_config import SearchConfig
    from src.services.linkedin import SearchResult

    config = SearchConfig(
        name="literal", position_text=position_text, query_text=query_text
    )
    path = tmp_path / "literal.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setattr(fetch_jobs, "get_settings", lambda: settings)
    searches = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def search(self, **kwargs):
            searches.append(kwargs)
            return SearchResult(records=[], skipped_known=0)

        def close(self):
            pass

    monkeypatch.setattr("src.services.fetch_runner.LinkedInClient", FakeClient)
    outcome = fetch_jobs.run_config_file(path, dry_run=dry_run)
    assert outcome.ok == bool(expected)
    if dry_run:
        assert searches == []
        assert capsys.readouterr().out.splitlines() == [
            f"[literal] would run {len(expected)} queries:",
            *[f"  - {query}" for query in expected],
        ]
    elif expected:
        assert outcome.summary.queries == expected
        assert len(searches) == 1
        assert searches[0]["queries"] == expected
        assert searches[0]["seniority"] == Seniority.junior
        assert searches[0]["requested_positions"] == position_text
    else:
        assert searches == []
