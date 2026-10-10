from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.recipient import RecipientStatus


class RecipientInput(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=500)
    recipient_email: EmailStr
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecipientStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recipient_id: str
    recipient_name: str
    recipient_email: EmailStr
    status: RecipientStatus
    error_message: str | None = None
    download_url: str | None = None
