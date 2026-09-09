import random
from datetime import UTC, datetime, timedelta
from typing import Any

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

WORK_MODELS = ["On-site", "Hybrid", "Remote"]

JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]

EXPERIENCE_LEVELS = [
    "Internship",
    "Entry level",
    "Associate",
    "Mid-Senior level",
]

STATUSES = ["New", "Applied", "Interview", "Rejected"]

JOB_SUMMARIES = [
    "Build and maintain machine-learning systems used by internal product teams.",
    "Develop data pipelines and predictive models for customer-facing applications.",
    "Work on production AI services, model evaluation, and deployment infrastructure.",
    "Design backend services and APIs for data-intensive applications.",
]

RESPONSIBILITIES = [
    [
        "Develop and maintain Python services.",
        "Train, evaluate, and deploy machine-learning models.",
        "Collaborate with software engineers and product managers.",
        "Monitor production systems and investigate model performance.",
    ],
    [
        "Create reusable data-processing pipelines.",
        "Build APIs using Python and modern web frameworks.",
        "Write automated tests and technical documentation.",
        "Participate in code reviews and architectural discussions.",
    ],
    [
        "Prototype new AI and machine-learning capabilities.",
        "Design evaluation datasets and model benchmarks.",
        "Improve inference latency and system reliability.",
        "Present experimental results to technical stakeholders.",
    ],
]

REQUIREMENTS = [
    [
        "Bachelor's or master's degree in Computer Science or a related subject.",
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
        "Experience with PyTorch, TensorFlow, or scikit-learn.",
        "Knowledge of model evaluation and experimentation.",
        "Familiarity with Docker and cloud infrastructure.",
        "Interest in applied AI research.",
    ],
]


def _create_random_description() -> str:
    summary = random.choice(JOB_SUMMARIES)
    responsibilities = random.choice(RESPONSIBILITIES)
    requirements = random.choice(REQUIREMENTS)

    responsibilities_text = "\n".join(f"- {item}" for item in responsibilities)
    requirements_text = "\n".join(f"- {item}" for item in requirements)

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


def create_random_job_payload(job_number: int) -> dict[str, Any]:
    posted_at = datetime.now(UTC) - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return {
        "title": random.choice(TITLES),
        "company": random.choice(COMPANIES),
        "location": random.choice(LOCATIONS),
        "work_model": random.choice(WORK_MODELS),
        "job_type": random.choice(JOB_TYPES),
        "experience_level": random.choice(EXPERIENCE_LEVELS),
        "posted_at": posted_at,
        "applicants": random.randint(1, 250),
        "status": random.choice(STATUSES),
        "url": f"https://example.com/jobs/{job_number}",
        "description": _create_random_description(),
    }
