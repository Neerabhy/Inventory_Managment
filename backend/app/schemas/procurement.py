from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class SupplierResponse(BaseModel):
    id: int
    supplier_name: str
    contact_email: EmailStr
    delivery_performance: float
    quality_score: float
    reliability: float
    cost_efficiency: float

    class Config:
        from_attributes = True

class VendorRecommendation(BaseModel):
    supplier_id: int
    supplier_name: str
    calculated_score: float
    unit_cost: float
    lead_time_days: int
    recommendation_tier: str  # BEST CHOICE, LOWEST COST, FASTEST DELIVERY

class ProcurementRecommendationResponse(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    suggested_reorder_quantity: int
    rankings: List[VendorRecommendation]

class PurchaseOrderCreate(BaseModel):
    product_id: int
    supplier_id: int
    warehouse_id: int
    quantity_ordered: int = Field(..., gt=0)
    procurement_cost: float = Field(..., gt=0.0)
    delivery_deadline: datetime
    
    # Override constraints tracking parameters
    override_flag: bool = False
    override_reason: Optional[str] = None

class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    product_id: int
    supplier_id: int
    warehouse_id: int
    quantity_ordered: int
    procurement_cost: float
    order_status: str
    created_at: datetime
    delivery_deadline: datetime

    class Config:
        from_attributes = True