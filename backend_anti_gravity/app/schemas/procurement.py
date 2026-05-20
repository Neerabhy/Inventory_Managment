"""
schemas/procurement.py — Pydantic v2 schemas for suppliers, purchase orders, and decisions.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Supplier ─────────────────────────────────────────────────────────
class SupplierCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=200)
    city: str
    state: str = "Unknown"
    country: str = "India"
    avg_lead_time_days: float = Field(default=7.0, ge=0)
    reliability_score: Optional[float] = Field(None, ge=0, le=1)
    defect_rate: Optional[float] = Field(None, ge=0, le=1)
    avg_cost_index: Optional[float] = Field(None, ge=0)
    on_time_delivery_rate: Optional[float] = Field(None, ge=0, le=1)


class SupplierUpdate(BaseModel):
    supplier_name: Optional[str] = None
    reliability_score: Optional[float] = Field(None, ge=0, le=1)
    avg_lead_time_days: Optional[float] = Field(None, ge=0)
    defect_rate: Optional[float] = Field(None, ge=0, le=1)


class SupplierOut(BaseModel):
    id: int
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: str = "India"
    reliability_score: Optional[float] = None
    avg_lead_time_days: Optional[float] = None
    defect_rate: Optional[float] = None
    avg_cost_index: Optional[float] = None
    on_time_delivery_rate: Optional[float] = None
    is_active: bool = True
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Vendor Ranking ───────────────────────────────────────────────────
class VendorRankResult(BaseModel):
    supplier_id: int
    supplier_name: str
    composite_score: float
    recommendation: str
    reliability_score: Optional[float] = None
    avg_lead_time_days: Optional[float] = None
    defect_rate: Optional[float] = None
    avg_cost_index: Optional[float] = None


# ── Purchase Order ───────────────────────────────────────────────────
class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)
    unit_price: Optional[float] = Field(None, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    delivery_city: str = Field(..., description="Must be a serviceable city")
    expected_delivery_date: Optional[str] = None
    notes: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = Field(..., min_length=1)


class PurchaseOrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Optional[str] = None
    total_price: Optional[str] = None

    model_config = {"from_attributes": True}


class PurchaseOrderOut(BaseModel):
    id: int
    order_number: Optional[str] = None
    supplier_id: int
    status: str = "DRAFT"
    total_amount: Optional[float] = None
    delivery_city: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    actual_delivery_date: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    items: list = []
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Procurement Decision ─────────────────────────────────────────────
class ProcurementDecisionCreate(BaseModel):
    order_id: int
    decision: str = Field(..., pattern="^(APPROVED|REJECTED|OVERRIDE)$")
    override_flag: bool = False
    override_reason: Optional[str] = None
    system_recommendation: Optional[str] = None


class ProcurementDecisionOut(BaseModel):
    id: int
    order_id: int
    decision: str = "APPROVED"
    override_flag: bool = False
    override_reason: Optional[str] = None
    system_recommendation: Optional[str] = None
    estimated_savings: Optional[float] = None
    notification_sent: bool = True
    decided_at: Optional[str] = None

    model_config = {"from_attributes": True}
