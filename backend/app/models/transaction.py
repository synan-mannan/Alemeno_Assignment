import uuid
from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Ingestion audit and lineage tracking
    txn_id = Column(String, nullable=True, index=True)
    original_txn_id = Column(String, nullable=True)
    
    date = Column(DateTime(timezone=True), nullable=True)
    original_date = Column(String, nullable=True)
    
    merchant = Column(String, nullable=True)
    original_merchant = Column(String, nullable=True)
    
    amount = Column(Float, nullable=True)
    original_amount = Column(String, nullable=True)
    
    currency = Column(String, nullable=True)
    original_currency = Column(String, nullable=True)
    
    status = Column(String, nullable=True)
    original_status = Column(String, nullable=True)
    
    category = Column(String, nullable=True)
    original_category = Column(String, nullable=True)
    
    account_id = Column(String, nullable=True, index=True)
    
    notes = Column(Text, nullable=True)
    original_notes = Column(Text, nullable=True)
    
    # Anomaly tracking
    is_anomaly = Column(Boolean, default=False, nullable=False, index=True)
    anomalies = Column(JSONB, nullable=True)  # List of anomaly JSONs: [{"rule": "...", "severity": "...", "confidence": 0.8, "reason": "..."}]
    
    # Lineage Metadata: Tracks exactly what transformations were applied (e.g. {"amount": {"modified": true, "original": "$100", "cleaned": 100.0}})
    cleaning_metadata = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    job = relationship("Job", back_populates="transactions")
