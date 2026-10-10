import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    issue_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipients: Mapped[list["JobRecipient"]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="JobRecipient.id")
