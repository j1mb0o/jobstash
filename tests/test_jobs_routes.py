from datetime import UTC

from fastapi.testclient import TestClient


def test_jobs_page_loads_table_shell(client: TestClient) -> None:
    response = client.get("/jobs")

    assert response.status_code == 200
    assert "Job database" in response.text
    assert 'id="jobs-table"' in response.text


def test_jobs_api_returns_stored_jobs(client: TestClient, add_job) -> None:
    job = add_job()

    response = client.get("/api/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    scraped_at = item.pop("scraped_at")
    assert scraped_at.endswith("+00:00")  # UTC marker lets the browser show local time
    assert item == {
        "id": job.id,
        "title": "Machine Learning Engineer",
        "company": "Northstar AI",
        "location": "Amsterdam",
        "work_model": "Hybrid",
        "job_type": "Full-time",
        "experience_level": "Entry level",
        "posted_at": "2026-08-05T10:30:00",
        "applicants": 14,
        "seniority_match_score": None,
        "url": "https://example.com/jobs/42",
    }


def test_job_detail_uses_locally_stored_description(
    client: TestClient, add_job
) -> None:
    job = add_job(
        title="Platform & Safety Engineer",
        description="Saved after the source disappeared. <script>alert(1)</script>",
    )

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    assert "Platform &amp; Safety Engineer" in response.text
    assert "Saved after the source disappeared." in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_job_detail_shows_seniority_score(client: TestClient, add_job) -> None:
    job = add_job(seniority_match_score=80)

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    assert "Seniority score" in response.text
    assert ">80<" in response.text


def test_job_detail_shows_scraped_time_in_local_timezone(
    client: TestClient, add_job
) -> None:
    job = add_job()
    expected = (
        job.scraped_at.replace(tzinfo=UTC).astimezone().strftime("%d %B %Y, %H:%M")
    )

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    assert expected in response.text


def test_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}
