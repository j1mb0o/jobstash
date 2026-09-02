from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import Settings, get_settings
from src.database import (
    Base,
    create_database_engine,
    create_session_factory,
    upgrade_schema,
)
from src.models import Job  # noqa: F401 - registers SQLAlchemy metadata
from src.routes.jobs import router as jobs_router
from src.routes.search import router as search_router

STATIC_PATH = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    engine = create_database_engine(runtime_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(engine)
        upgrade_schema(engine)
        yield
        engine.dispose()

    application = FastAPI(title="LinkedIn Job Search", lifespan=lifespan)
    application.state.session_factory = create_session_factory(engine)
    application.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")
    application.include_router(jobs_router)
    application.include_router(search_router)

    @application.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/search", status_code=303)

    return application


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "src.app:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
