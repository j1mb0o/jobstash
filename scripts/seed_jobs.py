import argparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database import Base, create_database_engine, create_session_factory
from src.models.job import Job
from src.services.seed import create_random_job_payload


def add_sample_jobs(session: Session, count: int) -> int:
    """Add `count` randomly generated jobs and return the new total."""
    largest_id = session.scalar(select(func.max(Job.id))) or 0
    jobs = [
        Job(**create_random_job_payload(largest_id + offset))
        for offset in range(1, count + 1)
    ]
    session.add_all(jobs)
    session.commit()
    return session.scalar(select(func.count()).select_from(Job)) or 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add sample jobs to the local database."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=30,
        help="Number of sample jobs to add (default: 30).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    engine = create_database_engine(get_settings().database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        total = add_sample_jobs(session, args.count)

    engine.dispose()
    print(f"Added {args.count} sample jobs. Database now contains {total} jobs.")


if __name__ == "__main__":
    main()
