import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import ScanRequest
from app.services.scanner import scanner_service


client = TestClient(app)


def test_root_and_health_endpoints():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["name"] == "LocalLeadPulse API"

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_start_scan_validation_error():
    # Limit must be between 1 and 100
    bad_payload = {
        "location": "Gandhinagar, Gujarat",
        "category": "Cafe",
        "limit": 0,
    }
    response = client.post("/api/leads/start", json=bad_payload)
    assert response.status_code == 422


def test_start_scan_and_get_results():
    payload = {
        "location": "Surat, Gujarat",
        "categories": ["Cafe"],
        "limit": 2,
    }
    # 1. Start scan (TestClient executes background_tasks before returning)
    start_res = client.post("/api/leads/start", json=payload)
    assert start_res.status_code == 201
    data = start_res.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert data["target_limit"] == 2
    assert "Cafe" in data["categories"]

    # 2. Check status
    status_res = client.get(f"/api/leads/status/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["job_id"] == job_id

    # 3. Results endpoint
    results_res = client.get(f"/api/leads/results/{job_id}")
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert results_data["is_completed"] is True
    assert results_data["qualified_count"] == 2
    assert len(results_data["leads"]) == 2
    for lead in results_data["leads"]:
        assert lead["category"] == "Cafe"
        assert "maps/search/?api=1" in lead["maps_url"]

    # 4. Download Excel workbook endpoint
    dl_res = client.get(f"/api/leads/download/{job_id}")
    assert dl_res.status_code == 200
    assert (
        dl_res.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(dl_res.content) > 1000


def test_stream_scan_progress_completed_job():
    # Setup job
    req = ScanRequest(
        location="Gandhinagar, Gujarat",
        category="Cafe",
        limit=1,
        use_mock=True,
    )
    job = scanner_service.create_job(req)
    asyncio.run(scanner_service.run_scan(job, delay_seconds=0.0))

    # Connect to stream
    with client.stream("GET", f"/api/leads/stream/{job.job_id}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunks = []
        for line in response.iter_lines():
            if line:
                chunks.append(line)
        assert len(chunks) > 0
        assert any("data:" in c for c in chunks)


def test_nonexistent_job_returns_404():
    res = client.get("/api/leads/status/nonexistent-999")
    assert res.status_code == 404

    res_res = client.get("/api/leads/results/nonexistent-999")
    assert res_res.status_code == 404

    res_dl = client.get("/api/leads/download/nonexistent-999")
    assert res_dl.status_code == 404
