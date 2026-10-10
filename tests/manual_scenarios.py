"""Run the requested fictional batch scenarios and keep PDFs in project storage."""
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import CERTIFICATE_STORAGE_DIR
from app.database import Base, get_db
from app.main import app
import app.main as main_module
import app.api.jobs as jobs_api
import app.tasks.worker as worker
from app.services.storage import StorageService


def main():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    main_module.engine = engine

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    worker.SessionLocal = session_factory
    jobs_api.process_certificate_batch = lambda job_id: None

    class FailOneRecipient:
        def __init__(self, real_generator):
            self.real_generator = real_generator

        def generate(self, **kwargs):
            if kwargs["recipient_name"] == "Casey Faulty Input":
                raise ValueError("Simulated rendering failure for scenario verification")
            return self.real_generator.generate(**kwargs)

    with TestClient(app) as client:
        scenarios = [
            ("one", "scenario_1_recipient.zip", [{"recipient_name": "Alex Example", "recipient_email": "alex@example.com"}], False),
            ("five_one_failure", "scenario_5_one_failure.zip", [
                {"recipient_name": "Blair Example", "recipient_email": "blair@example.com"},
                {"recipient_name": "Casey Faulty Input", "recipient_email": "casey@example.com"},
                {"recipient_name": "Devon Example", "recipient_email": "devon@example.com"},
                {"recipient_name": "Elliot Example", "recipient_email": "elliot@example.com"},
                {"recipient_name": "Finley Example", "recipient_email": "finley@example.com"},
            ], True),
            ("one_hundred", "scenario_100_recipients.zip", [
                {"recipient_name": f"Fictional Recipient {i:03}", "recipient_email": f"person{i:03}@example.com"}
                for i in range(1, 101)
            ], False),
            ("capacity_probe_1000", "capacity_probe_1000.zip", [
                {"recipient_name": f"Capacity Probe {i:04}", "recipient_email": f"probe{i:04}@example.com"}
                for i in range(1, 1001)
            ], False),
        ]
        for event_name, archive_name, recipients, inject_failure in scenarios:
            started = perf_counter()
            created = client.post("/api/v1/jobs", json={"event_name": f"Imaginary {event_name} event", "issue_date": "2026-10-09", "recipients": recipients})
            assert created.status_code == 202, created.text
            job_id = created.json()["job_id"]
            generator = None
            if inject_failure:
                from app.services.generator import CertificateGeneratorService
                generator = FailOneRecipient(CertificateGeneratorService())
            worker.process_certificate_batch(job_id, generator=generator)
            status_response = client.get(f"/api/v1/jobs/{job_id}")
            assert status_response.status_code == 200
            result = status_response.json()
            expected_status = "PARTIALLY_COMPLETED" if inject_failure else "COMPLETED"
            assert result["status"] == expected_status, result
            assert result["completed_count"] + result["failed_count"] == len(recipients)
            if event_name == "one":
                pdf_url = result["recipients"][0]["download_url"]
                assert client.get(pdf_url).headers["content-type"] == "application/pdf"
            if event_name == "five_one_failure":
                assert result["completed_count"] == 4 and result["failed_count"] == 1
                failed = next(r for r in result["recipients"] if r["status"] == "FAILED")
                assert failed["error_message"]
            if event_name == "one_hundred":
                assert result["completed_count"] == 100 and result["failed_count"] == 0
            successful_paths = [
                str(CERTIFICATE_STORAGE_DIR / job_id / f"{recipient['recipient_id']}.pdf")
                for recipient in result["recipients"]
                if recipient["status"] == "SUCCESS"
            ]
            archive_path = CERTIFICATE_STORAGE_DIR / archive_name
            with archive_path.open("wb") as archive_file:
                for chunk in StorageService.iter_zip(successful_paths):
                    archive_file.write(chunk)
            elapsed = perf_counter() - started
            print(f"{event_name}: job_id={job_id}, status={result['status']}, success={result['completed_count']}, failed={result['failed_count']}, elapsed_seconds={elapsed:.2f}, archive={archive_path}")
        print("configured_max_batch_size=none")
        print("capacity_probe=1000 recipients completed successfully; this is an observed tested size, not a finite maximum")

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


if __name__ == "__main__":
    main()
