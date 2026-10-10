import enum
import uuid
from typing import Any
from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RecipientStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class JobRecipient(Base):
    __tablename__ = "job_recipients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_name: Mapped[str] = mapped_column(String(500), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    status: Mapped[RecipientStatus] = mapped_column(Enum(RecipientStatus), default=RecipientStatus.PENDING, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    job: Mapped["Job"] = relationship(back_populates="recipients")
