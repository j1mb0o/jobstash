# AGENTS.md

# LinkedIn Job Search Tool

## Project Overview

This project is a local web application for discovering LinkedIn job postings, preserving their content, and reviewing the collected results through a searchable database interface.

The current scope is intentionally limited to:

- configuring LinkedIn job searches
- generating search queries from user input
- fetching job listings
- optionally fetching and storing full job descriptions
- saving fetched jobs to a local database
- browsing, sorting, filtering, and selecting stored jobs
- opening a dedicated formatted page for each stored job
- preserving job information when the original posting is removed

Do not add features beyond this scope unless explicitly requested; see Out of Scope.

## Commands

- Run server: `uv run uvicorn src.app:app --reload --port 1234`
- Run tests: `uv run pytest`
- Run one test file: `uv run pytest tests/test_scoring.py`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Seed dev data: `uv run python -m scripts.seed_jobs --count 50`

Ruff runs with its default configuration.

## Current Architecture Direction

The project is moving away from Gradio toward a conventional server-rendered web application.

Preferred stack:

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- SQLite
- Pydantic
- Jinja2 templates
- HTMX for small dynamic interactions
- Tabulator for the main job table
- plain CSS and minimal JavaScript

Avoid introducing React, Vue, or another frontend framework unless the existing approach can no longer reasonably support a requested feature.

## Core Design Principle

Keep scraping, persistence, business logic, and presentation separate.

Expected flow:

```text
Browser
  -> FastAPI route
  -> service layer
  -> repository or external client
  -> database or LinkedIn endpoint
```

The UI must not contain scraping logic, business logic, or direct SQL queries. The database remains authoritative; browser table state is temporary.

## Suggested Project Structure

```text
src/
├── app.py
├── config.py
├── database.py
├── models/
│   └── job.py
├── schemas/
│   ├── job.py
│   └── search.py
├── repositories/
│   └── jobs.py
├── services/
│   ├── jobs.py
│   ├── query_generation.py
│   └── linkedin.py
├── routes/
│   ├── jobs.py
│   └── search.py
├── templates/
│   ├── base.html
│   ├── search.html
│   ├── jobs/
│   │   ├── list.html
│   │   └── detail.html
│   └── components/
├── static/
│   ├── css/
│   │   └── app.css
│   └── js/
│       └── jobs-table.js
└── utils/
```

Do not create empty modules merely to match this structure. Add files only when their responsibility is needed.

## Main Pages

### Search Page

The search page owns the job-discovery workflow.

It may contain:

- positions or keywords
- country or location
- seniority
- LinkedIn experience level
- job type
- work model
- posting age
- Easy Apply filter
- applicant-count filter
- pages per query
- description-fetching option
- request delay
- generated and editable search queries
- fetch progress and result summary

The page should allow users to generate queries before fetching jobs.

### Jobs Database Page

This is the main interface for reviewing stored jobs.

It should support:

- sorting
- filtering
- search
- pagination
- row selection
- opening job details
- opening the original posting
- deleting selected jobs
- refreshing the displayed data

Use Tabulator functionality instead of implementing table features manually when possible.

### Job Detail Page

Each stored job should have a stable local URL such as:

```text
/jobs/{job_id}
```

The page should display:

- title
- company
- location
- work model
- job type
- experience level
- posting date
- applicant count, when available
- full locally stored description
- original job URL

The local detail page must continue to work even if the original LinkedIn posting disappears.

## Configuration

Runtime configuration belongs in environment variables and local `.env` files, not in a settings page.

Examples:

```env
DATABASE_URL=sqlite:///jobs.db
APP_HOST=127.0.0.1
APP_PORT=1234
LOG_LEVEL=INFO
DEFAULT_LOCATION=Netherlands
DEFAULT_REQUEST_DELAY_SECONDS=3
DEFAULT_FETCH_DESCRIPTIONS=true
```

Rules:

- load configuration through a typed settings object
- do not access `os.getenv()` throughout the codebase
- centralize configuration in `config.py`
- provide a `.env.example` containing safe placeholder values
- never commit `.env`, tokens, cookies, credentials, or private configuration
- environment variables are defaults, while values entered on the search page may override search-specific defaults for that request

Prefer `pydantic-settings` for typed configuration.

## Database Rules

SQLite is the current source of truth for stored jobs.

Use SQLAlchemy 2.0 syntax consistently.

Routes must not execute SQL directly. Database access should go through repository functions or a clearly separated data-access layer.

Job descriptions must be stored as full text, not only as previews.

A job should retain the original source URL, but the application must not depend on that URL remaining available.

Prevent obvious duplicates. Prefer a stable external job identifier when available. Otherwise use a carefully selected uniqueness strategy such as a normalized combination of source, title, company, location, and source URL.

Do not silently overwrite an existing full description with an empty or shorter value.

Use migrations when changing an established database schema. During the earliest prototype stage, deleting the development database may be acceptable only when explicitly communicated.

## LinkedIn Integration

All LinkedIn-specific behavior belongs in `services/linkedin.py` or a dedicated `services/linkedin/` package.

The LinkedIn client may:

- construct request parameters
- fetch result pages
- parse job cards
- fetch job-detail pages
- normalize source data
- handle retries, delays, and request errors

It must not:

- render HTML pages
- access UI components
- contain table-specific formatting

Use conservative request pacing and clear error handling. Do not add mechanisms intended to evade access controls, CAPTCHAs, authentication requirements, or platform protections.

Return structured domain data instead of raw HTML wherever practical.

## Service Boundaries

### Query Generation Service

Responsible for converting user-entered positions and seniority preferences into editable search queries.

It must be deterministic unless there is an explicit reason otherwise.

### LinkedIn Service

Responsible for retrieving and parsing external job data.

### Scoring Service

Responsible for deterministic seniority matching between requested and returned experience levels, including discarding jobs outside a fixed tolerance. It is rule-based, not AI; AI-based ranking remains out of scope.

### Job Service

Responsible for application-level operations such as:

- saving fetched jobs
- deduplicating results
- preserving existing descriptions
- retrieving job detail data
- deleting jobs

### Job Repository

Responsible only for database operations.

Do not mix HTTP parsing, business rules, and persistence in the same function.

### Seed Service

`services/seed.py` generates random sample jobs for development, invoked only through `scripts/seed_jobs.py`. It must not be called from application routes.

## API and Route Conventions

Prefer separate HTML routes and JSON endpoints when appropriate.

Example routes:

```text
GET    /                     -> redirect to search or jobs page
GET    /search               -> render search page
POST   /search/queries       -> generate editable queries
POST   /search/fetch         -> run a job search
GET    /jobs                 -> render jobs table page
GET    /jobs/{job_id}        -> render job detail page
GET    /api/jobs             -> return table data as JSON
DELETE /api/jobs/{job_id}    -> delete one job
POST   /api/jobs/bulk-delete -> delete selected jobs
```

Use appropriate HTTP status codes and structured error responses.

Do not expose SQLAlchemy models directly as API responses.

## Frontend Rules

Use server-rendered Jinja templates for page structure.

Use HTMX only for focused interactions where avoiding a full-page reload improves the workflow.

Use minimal standalone JavaScript for Tabulator configuration and features that HTMX does not handle well.

Maintain a consistent layout with shared templates and reusable components.

The interface should prioritize:

- clear hierarchy
- compact but readable forms
- efficient keyboard and mouse use
- visible progress during fetching
- actionable error messages
- predictable navigation

## Table Rules

The jobs table is a core component.

Use Tabulator for:

- column sorting
- filtering
- pagination
- row selection
- column resizing
- link or button formatters
- loading JSON data

Do not render the entire job description inside the table. Show a short preview or omit it and provide a detail action.

Selected row IDs should be sent to backend endpoints for bulk operations.

## Error Handling and Logging

Do not hide failures behind generic messages such as `Something went wrong`.

Log enough context to diagnose:

- failed search queries
- HTTP status codes
- parsing failures
- failed description requests
- database exceptions
- duplicate handling decisions

Do not log secrets, complete cookies, authorization headers, or sensitive environment values.

Expected external failures should be handled gracefully and shown to the user without crashing the server.

## Coding Standards

- use Python 3.12 or newer
- use type hints for public functions and meaningful internal boundaries
- use SQLAlchemy 2.0 style
- use clear domain names instead of generic names such as `data` or `item`
- keep functions focused
- avoid global mutable state
- prefer dependency injection through FastAPI dependencies or constructors
- avoid unnecessary abstractions
- use Ruff for linting and formatting
- keep imports organized
- add docstrings where behavior or constraints are not obvious

Do not introduce a pattern solely because it is fashionable. Use the smallest architecture that keeps responsibilities clear.

## Testing Expectations

Prioritize tests for behavior that can break silently.

Important test areas:

- query generation
- LinkedIn response parsing
- job normalization
- duplicate detection
- preservation of existing descriptions
- repository CRUD operations
- job-detail route behavior
- invalid job IDs
- bulk deletion

Mock external HTTP calls in automated tests.

Do not write tests that merely repeat implementation details or assert static enum labels without protecting meaningful behavior.

## Dependency Rules

Before adding a dependency:

1. confirm that the standard library or an existing dependency cannot handle the requirement cleanly
2. verify that the dependency is maintained
3. explain its role in the relevant change
4. avoid overlapping libraries that solve the same problem

Preferred dependencies are the stack listed above plus `uvicorn`, `httpx2`, `beautifulsoup4`, and `pytest`.

Use `httpx2` for HTTP clients, not `httpx`, which emits deprecation warnings.

Frontend libraries loaded from a CDN should have pinned versions. A local static copy may be preferable later.

## Out of Scope

Unless explicitly requested, do not implement:

- Notion integration
- application status tracking
- interview tracking
- job lifecycle workflows
- reminders or notifications
- user accounts
- authentication
- cloud deployment
- PostgreSQL migration
- AI-based ranking or summarization (deterministic seniority scoring is in scope)
- resume or cover-letter management
- analytics dashboards
- a settings page
- a JavaScript SPA

## Feature Worktree Workflow

When tasked to work on a new feature, first create a git worktree for that feature:

1. create the worktree one layer above the project root (sibling directory), with an appropriate branch name
2. do all feature work inside that worktree, not in the main checkout

Example:

```bash
git worktree add ../linked-better-job-search-<feature-name> -b feature/<feature-name>
```

- use a short kebab-case `<feature-name>` (e.g. `jobs-table-filters`)
- use `feature/<feature-name>` as the branch name unless the user specifies otherwise
- do not reuse or overwrite an existing worktree directory; pick a distinct name

## Agent Workflow

Before making changes:

1. inspect the existing project structure
2. read related models, services, routes, and templates
3. identify the smallest coherent change
4. preserve existing working behavior unless the task requires changing it
5. state any schema migration or dependency impact

While making changes:

1. keep UI, service, and persistence responsibilities separate
2. reuse existing code rather than duplicating it
3. preserve type safety
4. handle errors explicitly
5. avoid broad refactors unrelated to the requested task

After making changes:

1. run formatting and linting
2. run relevant tests
3. verify the affected page manually when practical
4. summarize changed files and behavior
5. mention any required environment variables, migrations, or install commands

## Definition of Done

A change is complete when:

- it satisfies the requested scope
- responsibilities remain separated
- database behavior is safe
- external failures are handled
- public interfaces are typed
- relevant tests pass
- formatting and linting pass
- setup changes are documented
- no unrelated features were added
