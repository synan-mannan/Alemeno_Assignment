from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class JobBase(BaseModel):
    filename: str
    filesize: int


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    progress: int
    raw_metadata: Optional[Dict[str, Any]] = None
    error_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class JobUploadResponse(BaseModel):
    job_id: UUID
    filename: str
    status: str
    message: str
