import uuid
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, default="PENDING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    progress = Column(Integer, nullable=False, default=0)  # 0 to 100
    filename = Column(String, nullable=False)
    filesize = Column(Integer, nullable=False)
    
    # Store JSON payloads detailing run duration, header validation, row counts
    raw_metadata = Column(JSONB, nullable=True)
    # Store validation errors per row (e.g., {"malformed_rows": [{"row_index": 5, "reason": "Missing date"}]})
    error_summary = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="job", cascade="all, delete-orphan")
    summary = relationship("JobSummary", back_populates="job", uselist=False, cascade="all, delete-orphan")
