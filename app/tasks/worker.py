from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
from app.services.generator import CertificateGeneratorService
from app.services.storage import StorageService


def process_certificate_batch(job_id: str, session_factory=None, generator=None) -> None:
    session_factory = session_factory or SessionLocal
    db: Session = session_factory()
    try:
        job = db.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            return
        job.status = JobStatus.IN_PROGRESS
        db.commit()
        generator = generator or CertificateGeneratorService()
        recipients = db.query(JobRecipient).filter(JobRecipient.job_id == job_id).all()
        for recipient in recipients:
            try:
                data = generator.generate(event_name=job.event_name, issue_date=job.issue_date, recipient_id=recipient.id, recipient_name=recipient.recipient_name, metadata=recipient.metadata_json or {})
                path = StorageService.save(job_id, recipient.id, data)
                recipient.status = RecipientStatus.SUCCESS
                recipient.file_path = str(path)
                recipient.error_message = None
                job.completed_count += 1
            except Exception as exc:
                recipient.status = RecipientStatus.FAILED
                recipient.error_message = str(exc)[:4000] or exc.__class__.__name__
                job.failed_count += 1
            db.commit()
        job.completed_at = datetime.now(timezone.utc)
        if job.failed_count == 0:
            job.status = JobStatus.COMPLETED
        elif job.completed_count:
            job.status = JobStatus.PARTIALLY_COMPLETED
        else:
            job.status = JobStatus.FAILED
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
