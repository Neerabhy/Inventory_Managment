from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class ProductBase(BaseModel):
    product_name: str = Field(..., max_length=150)
    category: str = Field(..., max_length=50)
    brand: str = Field(..., max_length=50)
    price: float = Field(..., gt=0.0)
    size: Optional[str] = None
    color: Optional[str] = None

class ProductCreate(ProductBase):
    product_code: Optional[str] = Field(None, description="Leave blank to trigger PRD-2026-XXXX naming structure.")

class ProductResponse(ProductBase):
    id: int
    product_code: str
    rating: float
    return_rate: float
    abc_class: str

    class Config:
        from_attributes = True

class InventoryResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    current_stock: int
    reserved_stock: int
    incoming_stock: int
    safety_stock: int
    reorder_point: int
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True

class StockAdjustmentRequest(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int = Field(..., ne=0, description="Positive to add, negative to consume.")
    movement_type: str = Field(..., description="ADJUSTMENT, INBOUND, OUTBOUND, or RETURN")
    reference_id: Optional[str] = None

class InventoryMovementResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    movement_type: str
    quantity: int
    stock_before: int
    stock_after: int
    reference_id: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True