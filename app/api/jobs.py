from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from app.database import get_db
from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
from app.schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.schemas.recipient import RecipientStatusResponse
from app.tasks.worker import process_certificate_batch

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = Job(event_name=payload.event_name, issue_date=payload.issue_date, status=JobStatus.PENDING, total_count=len(payload.recipients))
    job.recipients = [JobRecipient(recipient_name=r.recipient_name, recipient_email=str(r.recipient_email), metadata_json=r.metadata) for r in payload.recipients]
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_certificate_batch, job.id)
    return JobCreateResponse(job_id=job.id, status=job.status, total_recipients=job.total_count, created_at=job.created_at, status_check_url=f"/api/v1/jobs/{job.id}")


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).options(selectinload(Job.recipients)).filter(Job.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    recipients = [RecipientStatusResponse(recipient_id=r.id, recipient_name=r.recipient_name, recipient_email=r.recipient_email, status=r.status, error_message=r.error_message, download_url=f"/api/v1/certificates/{r.id}/download" if r.status == RecipientStatus.SUCCESS else None) for r in job.recipients]
    progress = ((job.completed_count + job.failed_count) / job.total_count * 100) if job.total_count else 0.0
    return JobStatusResponse(job_id=job.id, event_name=job.event_name, status=job.status, total_count=job.total_count, completed_count=job.completed_count, failed_count=job.failed_count, progress_percentage=progress, created_at=job.created_at, completed_at=job.completed_at, recipients=recipients)
