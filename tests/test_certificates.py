from app.services.generator import CertificateGeneratorService


def test_certificate_generation_returns_pdf_bytes():
    pdf = CertificateGeneratorService().generate(
        event_name="Test Event",
        issue_date="2026-10-10",
        recipient_id="verification-id",
        recipient_name="Taylor Example",
        metadata={"grade": "A", "issuer_name": "Test Organization"},
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


def test_individual_and_bulk_download(client, payload):
    result = client.post("/api/v1/jobs", json=payload)
    job_id = result.json()["job_id"]
    status = client.get(result.json()["status_check_url"]).json()
    recipient_url = next(r["download_url"] for r in status["recipients"] if r["download_url"])
    pdf = client.get(recipient_url)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    archive = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"


def test_missing_certificate_and_job(client):
    assert client.get("/api/v1/certificates/missing/download").status_code == 404
    assert client.get("/api/v1/jobs/missing/download-all").status_code == 404
