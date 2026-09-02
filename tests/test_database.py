from sqlalchemy import create_engine, inspect, text

from src.database import upgrade_schema


def test_upgrade_schema_adds_new_columns_to_existing_database(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'old-jobs.db'}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        )

    upgrade_schema(engine)
    upgrade_schema(engine)  # running twice must stay safe

    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    assert {"cv_match_score", "final_score"} <= columns


def test_upgrade_schema_ignores_fresh_databases(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")

    upgrade_schema(engine)

    assert inspect(engine).get_table_names() == []
