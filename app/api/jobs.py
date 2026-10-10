import csv
from io import StringIO
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload
from app.config import limiter
from app.database import get_db
from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
from app.schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.schemas.recipient import RecipientInput, RecipientStatusResponse
from app.tasks.worker import process_certificate_batch

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _create_job(payload: JobCreateRequest, background_tasks: BackgroundTasks, db: Session):
    job = Job(event_name=payload.event_name, issue_date=payload.issue_date, status=JobStatus.PENDING, total_count=len(payload.recipients))
    job.recipients = [JobRecipient(recipient_name=r.recipient_name, recipient_email=str(r.recipient_email), metadata_json=r.metadata) for r in payload.recipients]
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_certificate_batch, job.id)
    return JobCreateResponse(job_id=job.id, status=job.status, total_recipients=job.total_count, created_at=job.created_at, status_check_url=f"/api/v1/jobs/{job.id}")


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
def create_job(request: Request, payload: JobCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return _create_job(payload, background_tasks, db)


@router.post("/upload", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
def upload_job(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...), event_name: str = Form(...), issue_date: str | None = Form(None), db: Session = Depends(get_db)):
    try:
        text = file.file.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text), strict=True)
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row")
        headers = [header.strip().lower() for header in reader.fieldnames]
        if any(not header for header in headers) or len(headers) != len(set(headers)):
            raise ValueError("CSV headers must be non-empty and unique")
        recipients = []
        aliases = {"name", "recipient_name", "email", "recipient_email"}
        for line, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"CSV row {line} contains more fields than its header")
            row = {str(key).strip(): (value or "").strip() for key, value in raw.items() if key is not None}
            normalized = {key.lower(): value for key, value in row.items()}
            if not any(normalized.values()):
                continue
            try:
                recipients.append(RecipientInput.model_validate({
                    "recipient_name": normalized.get("recipient_name") or normalized.get("name"),
                    "recipient_email": normalized.get("recipient_email") or normalized.get("email"),
                    "metadata": {key: value for key, value in row.items() if key.lower() not in aliases},
                }))
            except ValidationError as exc:
                raise ValueError(f"CSV row {line} is invalid: {exc}") from exc
        payload = JobCreateRequest(event_name=event_name, issue_date=issue_date, recipients=recipients)
    except (UnicodeDecodeError, csv.Error, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}") from exc
    finally:
        file.file.close()
    return _create_job(payload, background_tasks, db)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).options(selectinload(Job.recipients)).filter(Job.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    recipients = [RecipientStatusResponse(recipient_id=r.id, recipient_name=r.recipient_name, recipient_email=r.recipient_email, status=r.status, error_message=r.error_message, download_url=f"/api/v1/certificates/{r.id}/download" if r.status == RecipientStatus.SUCCESS else None) for r in job.recipients]
    progress = ((job.completed_count + job.failed_count) / job.total_count * 100) if job.total_count else 0.0
    return JobStatusResponse(job_id=job.id, event_name=job.event_name, status=job.status, total_count=job.total_count, completed_count=job.completed_count, failed_count=job.failed_count, progress_percentage=progress, created_at=job.created_at, completed_at=job.completed_at, recipients=recipients)
