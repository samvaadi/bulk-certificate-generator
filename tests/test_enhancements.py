import threading
import time

from app.main import limiter
from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
import app.tasks.worker as worker


def test_csv_upload_job_creation(client):
    response = client.post(
        "/api/v1/jobs/upload",
        data={"event_name": "CSV Workshop", "issue_date": "2026-10-10"},
        files={"file": ("recipients.csv", b"name,email,department,grade\nAvery Example,avery@example.com,Engineering,A\nBlake Sample,blake@example.com,Design,B\n", "text/csv")},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["total_recipients"] == 2
    db = worker.SessionLocal()
    try:
        job = db.query(Job).filter_by(id=result["job_id"]).one()
        assert job.event_name == "CSV Workshop"
        assert job.issue_date == "2026-10-10"
        assert {r.recipient_name for r in job.recipients} == {"Avery Example", "Blake Sample"}
        metadata = {r.recipient_name: r.metadata_json for r in job.recipients}
        assert metadata["Avery Example"] == {"department": "Engineering", "grade": "A"}
    finally:
        db.close()


def test_rate_limiting_trigger(client):
    limiter._storage.reset()
    request = {"event_name": "Rate Test", "recipients": [{"recipient_name": "Test Recipient", "recipient_email": "test@example.com"}]}
    try:
        responses = [client.post("/api/v1/jobs", json=request) for _ in range(11)]
        assert all(response.status_code == 202 for response in responses[:10])
        assert responses[10].status_code == 429
    finally:
        limiter._storage.reset()


def test_concurrency_guard_execution(client, monkeypatch):
    monkeypatch.setattr(worker, "MAX_WORKERS", 2)
    db = worker.SessionLocal()
    job = Job(event_name="Concurrency Test", issue_date="2026-10-10", total_count=6, status=JobStatus.PENDING)
    job.recipients = [JobRecipient(recipient_name=f"Recipient {i}", recipient_email=f"person{i}@example.com") for i in range(6)]
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    lock = threading.Lock()
    active = 0
    peak = 0

    class ConcurrentGenerator:
        def generate(self, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return b"%PDF-1.4 test"

    worker.process_certificate_batch(job_id, generator=ConcurrentGenerator())
    db = worker.SessionLocal()
    try:
        completed = db.query(Job).filter_by(id=job_id).one()
        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_count == 6 and completed.failed_count == 0
        assert peak == 2
        assert peak <= worker.MAX_WORKERS
        assert all(recipient.status == RecipientStatus.SUCCESS for recipient in completed.recipients)
    finally:
        db.close()
