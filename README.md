# JobStash

<img src="src/static/img/logo.png" alt="JobStash logo" width="96">

A local FastAPI application for collecting and reviewing LinkedIn job postings.

## Run locally

Install the dependencies once:

```bash
uv sync --dev
```

Then launch the app with:

```bash
uv run uvicorn src.app:app --reload --port 1234
```

Open <http://127.0.0.1:1234/jobs>. Stop the server with `Ctrl+C`.

Runtime defaults can be overridden using the
variables documented in `.env.example`.

### Duplicate handling

Jobs already stored with a full description are recognized by their LinkedIn
job ID before any detail request is made, so re-fetching the same searches is
nearly free: only the search pages are requested again. Jobs stored without a
description (for example after a failed detail fetch) are re-fetched so a
later successful fetch repairs them, refreshing their scores alongside the
description.

### Add sample jobs

To add 50 randomly generated jobs to your local database, run:

```bash
uv run python -m scripts.seed_jobs --count 50
```

This adds rows without deleting jobs already in the database. If the app is
running, click **Refresh** on the job database page to see them.

The job database page loads persisted jobs from SQLite and opens each job at a
stable local URL (`/jobs/{job_id}`), where the full stored description remains
available independently of the source posting.

## How the backend fits together

If you come from machine learning, you can think of one web request as a small
inference pipeline:

```text
browser -> route -> repository -> SQLAlchemy -> SQLite
                         |
browser <- HTML or JSON <-+
```

- `src/app.py` creates the FastAPI application and connects all its parts.
- `src/config.py` validates configuration loaded from environment variables.
- `src/database.py` creates database engines and short-lived sessions.
- `src/models/job.py` defines how a job is stored in the SQL `jobs` table.
- `src/schemas/job.py` defines the validated shape returned by the application.
- `src/repositories/jobs.py` contains database reads. It is the only layer that
  needs to know the SQLAlchemy query syntax for this feature.
- `src/routes/jobs.py` maps URLs to repository calls and converts stored jobs to
  validated response schemas. A service layer can be added when job operations
  gain business rules that do not belong in either routes or repositories.
- `src/services/jobs.py` persists fetched jobs, deduplicates them (already
  stored jobs are skipped before scoring), and keeps stored descriptions safe.
- `src/services/scoring.py` computes the seniority match score and filters
  records outside the requested seniority tolerance.
- `src/templates/base.html` is the shared HTML shell.
- `src/templates/jobs/list.html` is the database page structure.
- `src/templates/jobs/detail.html` is the locally stored job-detail page.
- `src/static/css/app.css` controls presentation.
- `src/static/js/jobs-table.js` configures the interactive Tabulator table.
- `scripts/seed_jobs.py` is a development command that inserts random jobs.
- `tests/conftest.py` builds a fresh temporary database for every test.
- `tests/test_jobs_routes.py` checks the pages and API.
- `tests/test_seed_jobs.py` checks the sample-data command.
- `.env.example` documents safe runtime configuration values.
- `pyproject.toml` lists Python dependencies and project metadata.
- `uv.lock` pins exact dependency versions so installations are reproducible.

The small `__init__.py` files mark directories as importable Python packages and
occasionally expose their most useful classes. They contain no application logic.
