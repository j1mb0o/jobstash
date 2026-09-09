from fastapi.testclient import TestClient


def test_update_job_status(client: TestClient, add_job) -> None:
    job = add_job(status="New")

    response = client.patch(f"/api/jobs/{job.id}", json={"status": "Applied"})

    assert response.status_code == 200
    assert response.json()["status"] == "Applied"

    listed = client.get("/api/jobs").json()
    assert listed[0]["status"] == "Applied"


def test_update_job_status_rejects_unknown_value(client: TestClient, add_job) -> None:
    job = add_job()

    response = client.patch(f"/api/jobs/{job.id}", json={"status": "Hired-CEO"})

    assert response.status_code == 422


def test_update_missing_job_returns_404(client: TestClient) -> None:
    response = client.patch("/api/jobs/999999", json={"status": "Applied"})

    assert response.status_code == 404


def test_delete_job(client: TestClient, add_job) -> None:
    job = add_job()

    response = client.delete(f"/api/jobs/{job.id}")

    assert response.status_code == 204
    assert client.get(f"/jobs/{job.id}").status_code == 404
    assert client.get("/api/jobs").json() == []


def test_delete_missing_job_returns_404(client: TestClient) -> None:
    assert client.delete("/api/jobs/999999").status_code == 404


def test_bulk_delete_jobs(client: TestClient, add_job) -> None:
    first = add_job()
    second = add_job()
    kept = add_job()

    response = client.post(
        "/api/jobs/bulk-delete", json={"job_ids": [first.id, second.id]}
    )

    assert response.status_code == 200
    assert response.json() == {"requested": 2, "deleted": 2}
    remaining = client.get("/api/jobs").json()
    assert [item["id"] for item in remaining] == [kept.id]


def test_bulk_delete_rejects_empty_list(client: TestClient) -> None:
    response = client.post("/api/jobs/bulk-delete", json={"job_ids": []})

    assert response.status_code == 422


def test_bulk_update_status(client: TestClient, add_job) -> None:
    first = add_job(status="New")
    second = add_job(status="New")

    response = client.patch(
        "/api/jobs/bulk-status",
        json={"job_ids": [first.id, second.id], "status": "Applied"},
    )

    assert response.status_code == 200
    assert response.json() == {"requested": 2, "updated": 2, "status": "Applied"}
    statuses = {item["id"]: item["status"] for item in client.get("/api/jobs").json()}
    assert statuses[first.id] == "Applied"
    assert statuses[second.id] == "Applied"


def test_export_selected_jobs_as_json(client: TestClient, add_job) -> None:
    first = add_job(title="First")
    add_job(title="Second")

    response = client.get(f"/api/jobs/export?ids={first.id}")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == first.id
    assert payload[0]["description"] != ""


def test_export_all_jobs_when_no_ids(client: TestClient, add_job) -> None:
    add_job()
    add_job()

    response = client.get("/api/jobs/export")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_detail_page_shows_status_controls(client: TestClient, add_job) -> None:
    job = add_job(status="New")

    response = client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    assert 'id="status-form"' in response.text
    assert 'id="delete-job"' in response.text
    assert "<option" in response.text
