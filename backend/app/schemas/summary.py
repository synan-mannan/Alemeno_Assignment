from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MerchantSpend(BaseModel):
    merchant: str
    spend: float
    count: int


class JobSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    total_spend: Dict[str, float]
    top_merchants: List[MerchantSpend]
    anomaly_count: int
    financial_narrative: Optional[str] = None
    risk_level: str
    token_usage: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
