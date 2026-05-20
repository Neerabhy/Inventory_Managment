from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class KpiMetadataResponse(BaseModel):
    kpi_key: str
    display_name: str
    formula_text: str
    description_summary: str
    critical_threshold: Optional[float]

    class Config:
        from_attributes = True

class DashboardKpiSummary(BaseModel):
    kpi_key: str
    display_name: str
    computed_value: float
    variance_percentage: float
    is_critical_alert: bool

class ReturnEvaluationRequest(BaseModel):
    refund_status: str = Field(..., description="APPROVED or REJECTED")
    override_justification: Optional[str] = Field(None, max_length=255)

class ReturnRecordResponse(BaseModel):
    id: int
    product_id: int
    customer_id: int
    return_reason: str
    refund_status: str
    ai_risk_score: float
    is_human_override: bool
    override_justification: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True