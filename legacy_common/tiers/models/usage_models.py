# common/tiers/models/usage_models.py
from pydantic import BaseModel, Field
from datetime import datetime

class UsageRecord(BaseModel):
    tenant_id: str
    resource: str # e.g., 'embedding_tokens', 'ingested_documents'
    amount: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TenantUsage(BaseModel):
    daily_embedding_tokens: int = 0
    daily_documents: int = 0
