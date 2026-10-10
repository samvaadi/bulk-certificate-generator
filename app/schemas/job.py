from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.job import JobStatus
from app.schemas.recipient import RecipientInput, RecipientStatusResponse


class JobCreateRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=500)
    issue_date: str | None = Field(default=None, max_length=100)
    recipients: list[RecipientInput] = Field(min_length=1)


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    total_recipients: int
    created_at: datetime
    status_check_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    event_name: str
    status: JobStatus
    total_count: int
    completed_count: int
    failed_count: int
    progress_percentage: float
    created_at: datetime
    completed_at: datetime | None
    recipients: list[RecipientStatusResponse]
