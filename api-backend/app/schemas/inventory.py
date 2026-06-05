"""
schemas/inventory.py — Pydantic v2 schemas for inventory, products, movements, and suppliers.
"""
from __future__ import annotations
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Product ─────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    mrp: Optional[float] = Field(None, ge=0)
    selling_price: Optional[float] = Field(None, ge=0)
    manufacturing_cost: Optional[float] = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=0)
    fragile_flag: int = 0
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = None
    selling_price: Optional[float] = Field(None, ge=0)
    manufacturing_cost: Optional[float] = Field(None, ge=0)
    status: Optional[str] = None
    fragile_flag: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    product_code: Optional[str] = None
    name: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    mrp: Optional[float] = None
    selling_price: Optional[float] = None
    manufacturing_cost: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    return_rate: Optional[float] = None
    defect_rate: Optional[float] = None
    description: Optional[str] = None
    weight_kg: Optional[float] = None
    warranty_months: Optional[int] = None
    image_url: Optional[str] = None
    is_fragile: bool = False
    is_active: bool = True
    reorder_point: int = 10
    created_at: Optional[str] = None
    inventory_records: Optional[List['InventoryOut']] = None

    model_config = {"from_attributes": True}


# ── Inventory ────────────────────────────────────────────────────────
class InventoryUpdate(BaseModel):
    current_stock: Optional[int] = Field(None, ge=0)
    reserved_stock: Optional[int] = Field(None, ge=0)
    incoming_stock: Optional[int] = Field(None, ge=0)


class InventoryOut(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity_on_hand: int = 0
    quantity_reserved: int = 0
    quantity_in_transit: int = 0
    available_quantity: int = 0
    warehouse_location: Optional[str] = None
    warehouse_city: Optional[str] = None
    safety_stock: Optional[int] = None
    reorder_point: Optional[int] = None
    inventory_turnover: Optional[float] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Inventory Movement ───────────────────────────────────────────────
class MovementCreate(BaseModel):
    product_id: int
    movement_type: str = Field(..., pattern="^(STOCK_IN|STOCK_OUT|RETURN|ADJUSTMENT|TRANSFER|DAMAGE)$")
    quantity_delta: int = Field(..., description="Positive=inbound, negative=outbound")
    reference_id: Optional[str] = None
    note: Optional[str] = None


class MovementOut(BaseModel):
    id: int
    product_id: int
    movement_type: str
    quantity_delta: int = 0
    stock_before: int = 0
    stock_after: int = 0
    reference_id: Optional[str] = None
    note: Optional[str] = None
    performed_by: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Product-Supplier ─────────────────────────────────────────────────
class ProductSupplierCreate(BaseModel):
    supplier_id: int
    supplier_price: Optional[float] = Field(None, ge=0)
    lead_time_days: Optional[int] = Field(None, ge=0)
    minimum_order_qty: Optional[int] = Field(None, ge=1)
    supplier_rating: Optional[float] = Field(None, ge=0, le=5)
    preferred_supplier_flag: int = 0


class ProductSupplierOut(BaseModel):
    id: int
    product_id: int
    supplier_id: int
    supplier_price: Optional[float] = None
    lead_time_days: Optional[int] = None
    moq: Optional[int] = None
    supplier_rating: Optional[float] = None
    is_preferred: bool = False

    model_config = {"from_attributes": True}


# ── ABC Analysis ─────────────────────────────────────────────────────
class AbcItem(BaseModel):
    product_id: int
    product_name: str
    product_code: Optional[str] = None
    total_revenue: float
    revenue_pct: float
    cumulative_pct: float
    abc_class: str


class AbcAnalysisOut(BaseModel):
    items: List[AbcItem]
    total_products: int
    class_a_count: int
    class_b_count: int
    class_c_count: int


# ── KPI ──────────────────────────────────────────────────────────────
class KpiDefinitionOut(BaseModel):
    id: int
    kpi_code: str
    display_name: str
    description: Optional[str] = None
    formula: Optional[str] = None
    unit: Optional[str] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    higher_is_better: bool = True
    category: Optional[str] = None

    model_config = {"from_attributes": True}
