from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.recipient import JobRecipient, RecipientStatus
from app.models.job import Job
from app.services.storage import StorageService

router = APIRouter(tags=["certificates"])


@router.get("/certificates/{recipient_id}/download")
def download_certificate(recipient_id: str, db: Session = Depends(get_db)):
    recipient = db.query(JobRecipient).filter(JobRecipient.id == recipient_id).one_or_none()
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient.status != RecipientStatus.SUCCESS or not recipient.file_path:
        raise HTTPException(status_code=409, detail="Certificate is not available")
    path = StorageService.existing_path(recipient.file_path)
    if path is None:
        raise HTTPException(status_code=404, detail="Certificate file not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{recipient.id}.pdf")


@router.get("/jobs/{job_id}/download-all")
def download_all(job_id: str, db: Session = Depends(get_db)):
    if db.query(Job.id).filter(Job.id == job_id).first() is None:
        raise HTTPException(status_code=404, detail="Job not found")
    paths = [r.file_path for r in db.query(JobRecipient).filter(JobRecipient.job_id == job_id, JobRecipient.status == RecipientStatus.SUCCESS, JobRecipient.file_path.is_not(None)).all()]
    return StreamingResponse(StorageService.iter_zip(paths), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{job_id}.zip"'})
