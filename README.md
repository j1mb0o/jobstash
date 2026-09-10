# JobStash

A local web app for collecting LinkedIn job postings into a searchable SQLite archive, so listings stay readable even after the original posting disappears.

## Features

- **Search page** — enter positions and seniority, generate editable search queries, then fetch matching LinkedIn jobs with filters for location, experience level, job type, work model, posting age, Easy Apply, and applicant count.
- **Full descriptions** — optionally fetch and store the complete job description for every result, with conservative request pacing between detail requests.
- **Seniority matching** — deterministic, rule-based scoring discards jobs outside your seniority tolerance and scores the rest.
- **Jobs database** — sortable, filterable, paginated table (Tabulator) with row selection, full-text search, bulk delete, bulk status updates (`New` / `Applied` / `Interview` / `Rejected`), and JSON export.
- **Stable detail pages** — every stored job gets a local URL (`/jobs/{job_id}`) with the full saved description, independent of the source posting.
- **Safe re-fetching** — jobs already stored with a full description are recognized by LinkedIn job ID and skipped before any detail request; duplicates are deduplicated and existing descriptions are never overwritten with empty values.

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run uvicorn src.app:app --reload --port 1234
```

Open <http://127.0.0.1:1234> (`/` redirects to the search page). Stop with `Ctrl+C`.

To try the UI without fetching, seed 50 sample jobs:

```bash
uv run python -m scripts.seed_jobs --count 50
```

Then click **Refresh** on the job database page. Seeding only adds rows, never deletes.

## Workflow

1. **Search** — fill in positions, seniority, and filters; generate queries; review and edit them.
2. **Fetch** — run the search. Results are scored, deduplicated, and saved to SQLite with a progress summary (`new / already stored / duplicates / updated / discarded`).
3. **Review** — sort, filter, and search the jobs table; open detail pages; set statuses; export or delete in bulk.

## Configuration

All runtime settings come from environment variables (see `.env.example`), overridable per request from the search page:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///jobs.db` | SQLite database location |
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `1234` | Server bind address |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DEFAULT_LOCATION` | `Netherlands` | Pre-filled search location |
| `DEFAULT_REQUEST_DELAY_SECONDS` | `3` | Pacing between detail fetches |
| `DEFAULT_FETCH_DESCRIPTIONS` | `true` | Fetch full descriptions by default |
| `DEFAULT_SENIORITY` | `Junior` | Pre-selected seniority |

Copy `.env.example` to `.env` to customize. Never commit `.env` or credentials.

## Project layout

```text
src/
├── app.py             # FastAPI app, static files, router wiring
├── config.py          # Typed settings (pydantic-settings, no os.getenv elsewhere)
├── database.py        # Engine + session factory
├── models/            # SQLAlchemy table definitions
├── schemas/           # Pydantic request/response shapes
├── repositories/      # Database access only (no HTTP, no business rules)
├── services/          # linkedin client, query generation, scoring, job operations
├── routes/            # HTML pages + JSON API (no SQL, no scraping)
├── templates/         # Jinja2 server-rendered pages
└── static/            # CSS, Tabulator config, branding images
scripts/seed_jobs.py   # Dev-only sample data (never called from routes)
tests/                 # Parsing, scoring, dedup, repository, and route tests
```

Layer rule: `Browser → route → service → repository/client → database/LinkedIn`. The UI holds no scraping logic and routes run no SQL directly.

## Development

```bash
uv run pytest              # full test suite (external HTTP is mocked)
uv run pytest tests/test_scoring.py   # one file
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · SQLite · Pydantic · Jinja2 · HTMX · Tabulator · httpx2 · BeautifulSoup4 · pytest · Ruff

## Note

JobStash uses conservative request pacing and plain fetching with clear error handling — no evasion of access controls, CAPTCHAs, or auth. If LinkedIn rate-limits or blocks a request, the error is surfaced in the UI instead of crashing the server.
