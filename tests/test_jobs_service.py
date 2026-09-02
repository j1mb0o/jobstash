from src.models.job import Job
from src.schemas.search import JobDetails, JobRecord, Seniority
from src.services.jobs import (
    SaveSummary,
    known_job_ids_with_description,
    save_records,
)
from src.services.scoring import add_final_scores, add_seniority_match_scores


def make_record(
    job_id: str,
    *,
    title: str = "Machine Learning Engineer",
    description: str = "Build and operate ML systems.",
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        title=title,
        company="Example Co",
        location="Amsterdam, Netherlands",
        post_time="1 day ago",
        url=f"https://www.linkedin.com/jobs/view/{job_id}",
        search_query="Senior ML Engineer",
        seniority=Seniority.senior,
        requested_positions="ML engineer",
        status="New",
        details=JobDetails(
            description=description,
            criteria={
                "Seniority level": "Mid-Senior level",
                "Employment type": "Full-time",
            },
        ),
    )


def test_save_records_creates_new_jobs(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        summary = save_records(
            add_final_scores(
                add_seniority_match_scores(
                    [make_record("4123456789"), make_record("5123456789")]
                )
            ),
            session,
        )

    assert summary == SaveSummary(created=2, skipped=0, updated=0)
    with session_factory() as session:
        stored = session.query(Job).order_by(Job.linkedin_job_id).all()

    assert [job.linkedin_job_id for job in stored] == ["4123456789", "5123456789"]
    assert stored[0].description == "Build and operate ML systems."
    assert stored[0].experience_level == "Mid-Senior level"
    assert stored[0].seniority_match_score == 100
    assert stored[0].cv_match_score is None
    assert stored[0].final_score == 100
    assert stored[0].job_type == "Full-time"


def test_save_records_persists_cv_and_final_scores(client) -> None:
    session_factory = client.app.state.session_factory
    record = make_record("4123456789").model_copy(
        update={"cv_match_score": 0.5, "final_score": 44}
    )

    with session_factory() as session:
        save_records([record], session)

    with session_factory() as session:
        stored = session.query(Job).one()

    assert stored.cv_match_score == 0.5
    assert stored.final_score == 44


def test_save_records_skips_duplicates_with_same_linkedin_job_id(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        save_records([make_record("4123456789", description="original")], session)
        summary = save_records([make_record("4123456789", description="")], session)

    assert summary == SaveSummary(created=0, skipped=1, updated=0)
    with session_factory() as session:
        stored = session.query(Job).one()

    assert stored.description == "original"


def test_save_records_updates_description_when_incoming_is_longer(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        save_records([make_record("4123456789", description="short")], session)
        summary = save_records(
            [
                make_record(
                    "4123456789", description="a much longer description than short"
                )
            ],
            session,
        )

    assert summary == SaveSummary(created=0, skipped=0, updated=1)
    with session_factory() as session:
        stored = session.query(Job).one()

    assert stored.description == "a much longer description than short"


def test_save_records_refreshes_scores_when_description_updated(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        save_records([make_record("4123456789", description="short")], session)
        repaired = make_record(
            "4123456789", description="a much longer description than short"
        ).model_copy(update={"cv_match_score": 0.5, "final_score": 50})
        summary = save_records([repaired], session)

    assert summary == SaveSummary(created=0, skipped=0, updated=1)
    with session_factory() as session:
        stored = session.query(Job).one()

    assert stored.description == "a much longer description than short"
    assert stored.cv_match_score == 0.5
    assert stored.final_score == 50


def test_save_records_keeps_existing_scores_when_update_lacks_them(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        scored = make_record("4123456789", description="short").model_copy(
            update={"cv_match_score": 0.8, "final_score": 80}
        )
        save_records([scored], session)
        summary = save_records(
            [
                make_record(
                    "4123456789", description="a much longer description than short"
                )
            ],
            session,
        )

    assert summary == SaveSummary(created=0, skipped=0, updated=1)
    with session_factory() as session:
        stored = session.query(Job).one()

    assert stored.cv_match_score == 0.8
    assert stored.final_score == 80


def test_known_job_ids_with_description_returns_only_described_jobs(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        save_records(
            [
                make_record("4123456789", description="full description"),
                make_record("5123456789", description=""),
            ],
            session,
        )
        known = known_job_ids_with_description(session)

    assert known == {"4123456789"}


def test_save_records_skips_records_without_job_id(client) -> None:
    session_factory = client.app.state.session_factory

    with session_factory() as session:
        record = make_record("4123456789")
        record = record.model_copy(update={"job_id": ""})
        summary = save_records([record], session)

    assert summary == SaveSummary(created=0, skipped=0, updated=0)
    with session_factory() as session:
        assert session.query(Job).count() == 0
