from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
import app.tasks.worker as worker
from app.tasks.worker import process_certificate_batch


def test_create_job_returns_202_and_finishes(client, payload):
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert response.json()["total_recipients"] == 3
    status = client.get(response.json()["status_check_url"])
    assert status.status_code == 200
    assert status.json()["status"] == "COMPLETED"
    assert status.json()["progress_percentage"] == 100


def test_invalid_payloads_return_422(client, payload):
    payload["recipients"] = []
    assert client.post("/api/v1/jobs", json=payload).status_code == 422
    payload["recipients"] = [{"recipient_name": "A", "recipient_email": "bad-email"}]
    assert client.post("/api/v1/jobs", json=payload).status_code == 422


def test_failure_is_isolated(client, payload, monkeypatch):
    class OneFails:
        def generate(self, **kwargs):
            if kwargs["recipient_name"] == "Grace Hopper":
                raise ValueError("render failed")
            return b"%PDF-1.4 test"
    response = client.post("/api/v1/jobs", json=payload)
    job_id = response.json()["job_id"]
    # The TestClient background task has already completed; reset and replay with the faulting generator.
    db = worker.SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).one()
        job.status = JobStatus.PENDING
        job.completed_count = job.failed_count = 0
        for recipient in job.recipients:
            recipient.status = RecipientStatus.PENDING
            recipient.file_path = recipient.error_message = None
        db.commit()
    finally:
        db.close()
    process_certificate_batch(job_id, generator=OneFails())
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "PARTIALLY_COMPLETED"
    assert status["completed_count"] == 2 and status["failed_count"] == 1
    failed = next(r for r in status["recipients"] if r["recipient_name"] == "Grace Hopper")
    assert failed["error_message"] == "render failed"


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/jobs/missing").status_code == 404
