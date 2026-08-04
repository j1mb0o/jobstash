import os
import random
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import gradio as gr
import pandas as pd
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


DATABASE_PATH = Path("jobs.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    work_model: Mapped[str] = mapped_column(String(50), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    experience_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    applicants: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )


TITLES = [
    "Machine Learning Engineer",
    "Data Scientist",
    "AI Engineer",
    "Research Engineer",
    "Backend Developer",
    "Python Developer",
    "MLOps Engineer",
    "Junior Software Engineer",
]

COMPANIES = [
    "Northstar AI",
    "Delta Analytics",
    "BluePeak Systems",
    "Vector Labs",
    "Orion Technologies",
    "Nimbus Data",
    "Atlas Robotics",
    "QuantumWorks",
]

LOCATIONS = [
    "Amsterdam",
    "Rotterdam",
    "Leiden",
    "Utrecht",
    "The Hague",
    "Eindhoven",
]

WORK_MODELS = [
    "On-site",
    "Hybrid",
    "Remote",
]

JOB_TYPES = [
    "Full-time",
    "Part-time",
    "Contract",
    "Internship",
]

EXPERIENCE_LEVELS = [
    "Internship",
    "Entry level",
    "Associate",
    "Mid-Senior level",
]

STATUSES = [
    "New",
    "Interested",
    "Applied",
    "Interview",
    "Rejected",
]

JOB_SUMMARIES = [
    (
        "Build and maintain machine-learning systems used by "
        "internal product teams."
    ),
    (
        "Develop data pipelines and predictive models for "
        "customer-facing applications."
    ),
    (
        "Work on production AI services, model evaluation, "
        "and deployment infrastructure."
    ),
    (
        "Design backend services and APIs for data-intensive "
        "applications."
    ),
]

RESPONSIBILITIES = [
    [
        "Develop and maintain Python services.",
        "Train, evaluate, and deploy machine-learning models.",
        (
            "Collaborate with software engineers and "
            "product managers."
        ),
        (
            "Monitor production systems and investigate "
            "model performance."
        ),
    ],
    [
        "Create reusable data-processing pipelines.",
        "Build APIs using Python and modern web frameworks.",
        "Write automated tests and technical documentation.",
        (
            "Participate in code reviews and architectural "
            "discussions."
        ),
    ],
    [
        "Prototype new AI and machine-learning capabilities.",
        "Design evaluation datasets and model benchmarks.",
        "Improve inference latency and system reliability.",
        (
            "Present experimental results to technical "
            "stakeholders."
        ),
    ],
]

REQUIREMENTS = [
    [
        (
            "Bachelor's or master's degree in Computer Science "
            "or a related subject."
        ),
        "Experience with Python and SQL.",
        "Understanding of machine-learning fundamentals.",
        "Good written and verbal communication skills.",
    ],
    [
        "Experience with Python backend development.",
        "Familiarity with relational databases.",
        "Knowledge of Git and automated testing.",
        "Ability to work independently and within a team.",
    ],
    [
        (
            "Experience with PyTorch, TensorFlow, or "
            "scikit-learn."
        ),
        "Knowledge of model evaluation and experimentation.",
        "Familiarity with Docker and cloud infrastructure.",
        "Interest in applied AI research.",
    ],
]

TABLE_COLUMNS = [
    "id",
    "title",
    "company",
    "location",
    "work_model",
    "job_type",
    "experience_level",
    "posted_at",
    "applicants",
    "status",
    "description",
    "details",
    "url",
]


CUSTOM_CSS = """
.gradio-container {
    max-width: 100% !important;
    padding: 16px !important;
}

/* Buttons */
.toolbar button {
    min-height: 52px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 8px;
}

/* Status message */
.status-box textarea {
    min-height: 52px !important;
    font-size: 16px !important;
}

/* Table container */
.jobs-table {
    border: 1px solid var(--border-color-primary);
    border-radius: 8px;
    overflow: hidden;
}

/* Prevent headers and values from wrapping */
.jobs-table th,
.jobs-table td {
    white-space: nowrap !important;
    vertical-align: middle !important;
}

/* Header formatting */
.jobs-table th {
    padding: 14px 12px !important;
    font-size: 15px !important;
    font-weight: 700 !important;
}

/* Cell formatting */
.jobs-table td {
    padding: 12px !important;
    font-size: 15px !important;
}

/* Right-align ID and applicant count */
.jobs-table th:nth-child(1),
.jobs-table td:nth-child(1),
.jobs-table th:nth-child(9),
.jobs-table td:nth-child(9) {
    text-align: right !important;
}

/* Links */
.jobs-table a {
    text-decoration: underline;
    font-weight: 600;
}
"""


JOB_PAGE_CSS = """
:root {
    color-scheme: light dark;
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #f5f6f8;
    color: #1f2937;
}

.page {
    width: min(920px, calc(100% - 32px));
    margin: 40px auto;
}

.job-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 36px;
    box-shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 26px;
}

h1 {
    margin: 0 0 8px;
    font-size: 34px;
    line-height: 1.2;
}

.company {
    margin: 0;
    color: #4b5563;
    font-size: 19px;
}

.metadata {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 24px 0;
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 7px 12px;
    border: 1px solid #d1d5db;
    border-radius: 999px;
    background: #f9fafb;
    font-size: 14px;
}

.status {
    font-weight: 700;
}

.description {
    margin-top: 32px;
    font-size: 16px;
    line-height: 1.75;
    white-space: pre-wrap;
}

.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 32px;
}

.button {
    display: inline-block;
    padding: 11px 18px;
    border-radius: 9px;
    background: #2563eb;
    color: white;
    text-decoration: none;
    font-weight: 650;
}

.button.secondary {
    background: #374151;
}

@media (max-width: 640px) {
    .page {
        margin: 16px auto;
    }

    .job-card {
        padding: 24px;
    }

    .header {
        flex-direction: column;
    }

    h1 {
        font-size: 28px;
    }
}

@media (prefers-color-scheme: dark) {
    body {
        background: #111827;
        color: #f3f4f6;
    }

    .job-card {
        background: #1f2937;
        border-color: #374151;
    }

    .company {
        color: #d1d5db;
    }

    .badge {
        background: #111827;
        border-color: #4b5563;
    }
}
"""


def create_database() -> None:
    Base.metadata.create_all(engine)


def create_random_description() -> str:
    summary = random.choice(JOB_SUMMARIES)
    responsibilities = random.choice(RESPONSIBILITIES)
    requirements = random.choice(REQUIREMENTS)

    responsibilities_text = "\n".join(
        f"- {item}" for item in responsibilities
    )

    requirements_text = "\n".join(
        f"- {item}" for item in requirements
    )

    return f"""About the role

{summary}

Responsibilities

{responsibilities_text}

Requirements

{requirements_text}

What we offer

- Flexible working arrangements
- Personal development budget
- Modern engineering environment
- Competitive salary and benefits
"""


def create_random_job(job_number: int) -> Job:
    posted_at = datetime.now() - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    return Job(
        title=random.choice(TITLES),
        company=random.choice(COMPANIES),
        location=random.choice(LOCATIONS),
        work_model=random.choice(WORK_MODELS),
        job_type=random.choice(JOB_TYPES),
        experience_level=random.choice(EXPERIENCE_LEVELS),
        posted_at=posted_at,
        applicants=random.randint(1, 250),
        status=random.choice(STATUSES),
        url=f"https://example.com/jobs/{job_number}",
        description=create_random_description(),
    )


def seed_database(number_of_jobs: int = 30) -> None:
    with Session(engine) as session:
        existing_jobs = session.scalar(
            select(func.count()).select_from(Job)
        )

        if existing_jobs:
            return

        jobs = [
            create_random_job(job_number)
            for job_number in range(1, number_of_jobs + 1)
        ]

        session.add_all(jobs)
        session.commit()


def create_description_preview(
    description: str,
    maximum_length: int = 100,
) -> str:
    cleaned_description = " ".join(description.split())

    if len(cleaned_description) <= maximum_length:
        return cleaned_description

    return (
        cleaned_description[:maximum_length].rstrip()
        + "..."
    )


def load_jobs() -> pd.DataFrame:
    with Session(engine) as session:
        jobs = session.scalars(
            select(Job).order_by(Job.id.asc())
        ).all()

    records = [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "work_model": job.work_model,
            "job_type": job.job_type,
            "experience_level": job.experience_level,
            "posted_at": job.posted_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "applicants": job.applicants,
            "status": job.status,
            "description": create_description_preview(
                job.description
            ),
            "details": (
                f'<a href="/jobs/{job.id}" '
                f'target="_blank" '
                f'rel="noopener noreferrer">'
                f"View details"
                f"</a>"
            ),
            "url": (
                f'<a href="{escape(job.url, quote=True)}" '
                f'target="_blank" '
                f'rel="noopener noreferrer">'
                f"Original posting"
                f"</a>"
            ),
        }
        for job in jobs
    ]

    return pd.DataFrame(
        records,
        columns=TABLE_COLUMNS,
    )

################################## THIS WILL BE REMOVED ###############################
def refresh_jobs() -> tuple[pd.DataFrame, str]:
    return load_jobs(), "Jobs refreshed."


def add_random_job() -> tuple[pd.DataFrame, str]:
    with Session(engine) as session:
        largest_id = (
            session.scalar(select(func.max(Job.id)))
            or 0
        )

        job = create_random_job(largest_id + 1)
        job.status = "New"

        session.add(job)
        session.commit()

    return load_jobs(), "Added one random job."


def clear_database() -> tuple[pd.DataFrame, str]:
    with Session(engine) as session:
        session.execute(delete(Job))
        session.commit()

    return load_jobs(), "Deleted all jobs."


def reset_database() -> tuple[pd.DataFrame, str]:
    with Session(engine) as session:
        session.execute(delete(Job))
        session.commit()

    seed_database(number_of_jobs=30)

    return (
        load_jobs(),
        "Database reset with 30 random jobs.",
    )
#######################################################################################

def render_job_page(job: Job) -> str:
    title = escape(job.title)
    company = escape(job.company)
    location = escape(job.location)
    work_model = escape(job.work_model)
    job_type = escape(job.job_type)
    experience_level = escape(job.experience_level)
    status = escape(job.status)
    description = escape(job.description)
    original_url = escape(job.url, quote=True)

    posted_at = job.posted_at.strftime(
        "%d %B %Y at %H:%M"
    )

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1"
        >
        <title>{title} at {company}</title>
        <style>{JOB_PAGE_CSS}</style>
    </head>

    <body>
        <main class="page">
            <article class="job-card">
                <header class="header">
                    <div>
                        <h1>{title}</h1>
                        <p class="company">{company}</p>
                    </div>

                    <span class="badge status">
                        {status}
                    </span>
                </header>

                <section class="metadata">
                    <span class="badge">
                        {location}
                    </span>

                    <span class="badge">
                        {work_model}
                    </span>

                    <span class="badge">
                        {job_type}
                    </span>

                    <span class="badge">
                        {experience_level}
                    </span>

                    <span class="badge">
                        {job.applicants} applicants
                    </span>

                    <span class="badge">
                        Posted {posted_at}
                    </span>
                </section>

                <section class="description">
                    {description}
                </section>

                <footer class="actions">
                    <a
                        class="button"
                        href="{original_url}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        Open original posting
                    </a>

                    <a
                        class="button secondary"
                        href="/"
                    >
                        Return to database
                    </a>
                </footer>
            </article>
        </main>
    </body>
    </html>
    """


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="Job Database",
        theme=gr.themes.Base(),
        css=CUSTOM_CSS,
    ) as demo:
        gr.Markdown("# Job Database")

        with gr.Row(
            elem_classes="toolbar",
            equal_height=True,
        ):
            refresh_button = gr.Button(
                "↻ Refresh",
                variant="secondary",
                scale=1,
            )

            add_button = gr.Button(
                "＋ Add Random Job",
                variant="primary",
                scale=1,
            )

            reset_button = gr.Button(
                "↻ Reset Data",
                scale=1,
            )

            clear_button = gr.Button(
                "🗑 Clear Database",
                variant="stop",
                scale=1,
            )

        status_message = gr.Textbox(
            value="Database ready.",
            label=None,
            interactive=False,
            container=True,
            elem_classes="status-box",
        )

        gr.Markdown("## Jobs")

        jobs_table = gr.Dataframe(
            value=load_jobs,
            headers=TABLE_COLUMNS,
            datatype=[
                "number",
                "str",
                "str",
                "str",
                "str",
                "str",
                "str",
                "str",
                "number",
                "str",
                "str",
                "html",
                "html",
            ],
            column_widths=[
                "60px",
                "210px",
                "190px",
                "130px",
                "110px",
                "120px",
                "170px",
                "190px",
                "100px",
                "110px",
                "300px",
                "120px",
                "140px",
            ],
            label=None,
            interactive=False,
            wrap=False,
            max_height=620,
            elem_classes="jobs-table",
        )

        refresh_button.click(
            fn=refresh_jobs,
            outputs=[
                jobs_table,
                status_message,
            ],
        )

        add_button.click(
            fn=add_random_job,
            outputs=[
                jobs_table,
                status_message,
            ],
        )

        reset_button.click(
            fn=reset_database,
            outputs=[
                jobs_table,
                status_message,
            ],
        )

        clear_button.click(
            fn=clear_database,
            outputs=[
                jobs_table,
                status_message,
            ],
        )

    return demo


load_dotenv()

create_database()
seed_database()

fastapi_app = FastAPI(
    title="Job Database",
)


@fastapi_app.get(
    "/jobs/{job_id}",
    response_class=HTMLResponse,
)
def job_details(job_id: int) -> HTMLResponse:
    with Session(engine) as session:
        job = session.get(Job, job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Job not found.",
            )

        html = render_job_page(job)

    return HTMLResponse(content=html)


app = gr.mount_gradio_app(
    fastapi_app,
    build_app(),
    path="/",
)


def main() -> None:
    server_port = int(
        os.getenv(
            "GRADIO_SERVER_PORT",
            "1234",
        )
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=server_port,
    )


if __name__ == "__main__":
    main()