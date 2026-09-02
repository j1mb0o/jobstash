from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


SCHEMA_UPGRADES: dict[str, str] = {
    "cv_match_score": "ALTER TABLE jobs ADD COLUMN cv_match_score FLOAT",
    "final_score": "ALTER TABLE jobs ADD COLUMN final_score INTEGER",
}


def create_database_engine(database_url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(database_url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def upgrade_schema(engine: Engine) -> None:
    """Add columns introduced after the first release to existing databases.

    Fresh databases already contain every column because ``create_all``
    builds the current schema; this only patches databases created earlier.
    """
    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("jobs")}
    with engine.begin() as connection:
        for column_name, statement in SCHEMA_UPGRADES.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
