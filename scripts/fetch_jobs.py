"""CLI to run saved search configs without the browser.

Examples:
    uv run python -m scripts.fetch_jobs --all
    uv run python -m scripts.fetch_jobs --config configs/ml-nl-junior.json
    uv run python -m scripts.fetch_jobs --config "ml-nl-junior" --dry-run
    uv run python -m scripts.fetch_jobs --config a.json --config b.json --dry-run
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx2

from src.config import get_settings
from src.database import Base, create_database_engine, create_session_factory
from src.services.fetch_runner import (
    EmptyQueryError,
    FetchSummary,
    resolve_fetch_queries,
)
from src.services.fetch_runner import run_fetch as run_single_fetch
from src.services.search_configs import (
    SearchConfigError,
    find_config_file,
    list_config_files,
    load_config_file,
)

logger = logging.getLogger("fetch_jobs")


@dataclass
class ConfigOutcome:
    name: str
    ok: bool
    summary: FetchSummary | None = None
    error: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run saved LinkedIn search configs (configs/*.json)."
    )
    select = parser.add_mutually_exclusive_group(required=True)
    select.add_argument(
        "--all",
        action="store_true",
        help="Run every configs/*.json file (skips *.example.json).",
    )
    select.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="NAME|PATH",
        help="Run one saved config by name, stem, or file path "
        "(e.g. configs/ml.json — tab-completes). Repeatable.",
    )
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Override SEARCH_CONFIG_DIR (default: from settings).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configs and print resolved queries without fetching.",
    )
    parser.add_argument(
        "--stagger-seconds",
        type=float,
        default=None,
        help="Sleep between configs (default: FETCH_STAGGER_SECONDS setting).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def discover_configs(config_dir: Path, names: list[str], run_all: bool) -> list[Path]:
    if run_all:
        files = list_config_files(config_dir)
        if not files:
            raise SearchConfigError(f"No search configs found in {config_dir}.")
        return files
    return [find_config_file(config_dir, name) for name in names]


def run_config_file(path: Path, *, dry_run: bool) -> ConfigOutcome:
    try:
        config = load_config_file(path)
    except SearchConfigError as exc:
        return ConfigOutcome(name=path.stem, ok=False, error=str(exc))

    params = config.to_fetch_params()
    if dry_run:
        queries = resolve_fetch_queries(params)
        print(f"[{config.name}] would run {len(queries)} queries:")
        for query in queries:
            print(f"  - {query}")
        if not queries:
            return ConfigOutcome(
                name=config.name, ok=False, error="No queries resolved."
            )
        return ConfigOutcome(
            name=config.name,
            ok=True,
            summary=None,
        )

    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            try:
                summary = run_single_fetch(params, session)
            except EmptyQueryError as exc:
                return ConfigOutcome(name=config.name, ok=False, error=str(exc))
            except httpx2.HTTPStatusError as exc:
                return ConfigOutcome(
                    name=config.name,
                    ok=False,
                    error=f"LinkedIn returned HTTP {exc.response.status_code}.",
                )
            except httpx2.HTTPError as exc:
                return ConfigOutcome(
                    name=config.name, ok=False, error=f"LinkedIn request failed: {exc}"
                )
    finally:
        engine.dispose()
    print(f"[{config.name}] {summary.message} Queries: {', '.join(summary.queries)}")
    return ConfigOutcome(name=config.name, ok=True, summary=summary)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    config_dir = Path(args.config_dir or settings.search_config_dir)
    stagger = (
        args.stagger_seconds
        if args.stagger_seconds is not None
        else settings.fetch_stagger_seconds
    )

    try:
        files = discover_configs(config_dir, args.config, args.all)
    except SearchConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    outcomes: list[ConfigOutcome] = []
    for index, path in enumerate(files):
        if index > 0 and stagger > 0 and not args.dry_run:
            logger.info("Sleeping %.1fs before next config...", stagger)
            time.sleep(stagger)
        outcomes.append(run_config_file(path, dry_run=args.dry_run))

    succeeded = sum(1 for outcome in outcomes if outcome.ok)
    failed = len(outcomes) - succeeded
    total_new = sum(
        outcome.summary.new_jobs for outcome in outcomes if outcome.summary is not None
    )
    print(f"Done: {succeeded} succeeded, {failed} failed, {total_new} new jobs.")
    for outcome in outcomes:
        if not outcome.ok:
            print(f"  FAILED {outcome.name}: {outcome.error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
