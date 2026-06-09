from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    
    txn_id: Optional[str] = None
    original_txn_id: Optional[str] = None
    
    date: Optional[datetime] = None
    original_date: Optional[str] = None
    
    merchant: Optional[str] = None
    original_merchant: Optional[str] = None
    
    amount: Optional[float] = None
    original_amount: Optional[str] = None
    
    currency: Optional[str] = None
    original_currency: Optional[str] = None
    
    status: Optional[str] = None
    original_status: Optional[str] = None
    
    category: Optional[str] = None
    original_category: Optional[str] = None
    
    account_id: Optional[str] = None
    notes: Optional[str] = None
    original_notes: Optional[str] = None
    
    is_anomaly: bool
    anomalies: Optional[List[Dict[str, Any]]] = None
    cleaning_metadata: Optional[Dict[str, Any]] = None
    
    created_at: datetime
    updated_at: datetime
