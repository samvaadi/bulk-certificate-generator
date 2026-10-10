from datetime import datetime, timezone
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from sqlalchemy.orm import Session
from app.config import MAX_WORKERS
from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.recipient import JobRecipient, RecipientStatus
from app.services.generator import CertificateGeneratorService
from app.services.storage import StorageService


def _generate_and_save(generator, job_id, recipient_id, event_name, issue_date, recipient_name, metadata):
    data = generator.generate(event_name=event_name, issue_date=issue_date, recipient_id=recipient_id, recipient_name=recipient_name, metadata=metadata or {})
    path = StorageService.save(job_id, recipient_id, data)
    return str(path)


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
        tasks = iter((r.id, r.recipient_name, r.metadata_json) for r in recipients)
        pending = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            exhausted = False
            while pending or not exhausted:
                while len(pending) < MAX_WORKERS and not exhausted:
                    try:
                        recipient_id, recipient_name, metadata = next(tasks)
                    except StopIteration:
                        exhausted = True
                        break
                    future = executor.submit(_generate_and_save, generator, job_id, recipient_id, job.event_name, job.issue_date, recipient_name, metadata)
                    pending[future] = recipient_id
                if not pending:
                    break
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    recipient_id = pending.pop(future)
                    recipient = db.query(JobRecipient).filter(JobRecipient.id == recipient_id).one()
                    try:
                        recipient.file_path = future.result()
                        recipient.status = RecipientStatus.SUCCESS
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
