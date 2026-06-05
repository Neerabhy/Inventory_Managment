"""
api/procurement.py — Procurement routes: suppliers, purchase orders, vendor ranking, decisions.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend_anti_gravity.app.api.deps import get_current_user, get_db, require_procurement
from backend_anti_gravity.app.core.config import settings
from backend_anti_gravity.app.ml.vendor_ranker import VendorRanker
from app.models.auth import User
from app.models.procurement import (
    ProcurementDecision, PurchaseOrder, Supplier,
)
from app.schemas.procurement import (
    ProcurementDecisionCreate, ProcurementDecisionOut,
    PurchaseOrderCreate, PurchaseOrderOut,
    SupplierCreate, SupplierOut, SupplierUpdate, VendorRankResult,
)

router = APIRouter(prefix="/procurement", tags=["Procurement"])


# ── Suppliers ─────────────────────────────────────────────────────────
@router.get("/suppliers", response_model=List[SupplierOut])
async def list_suppliers(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all suppliers, optionally filtering by active status."""
    q = select(Supplier)
    if is_active is not None:
        q = q.where(Supplier.is_active == is_active)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Create a new supplier record."""
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = await db.get(Supplier, supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return s


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_procurement),
):
    """Partially update supplier performance metrics."""
    s = await db.get(Supplier, supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.commit()
    await db.refresh(s)
    return s


# ── Vendor Ranking ───────────────────────────────────────────────────
@router.get("/suppliers/rank/{product_id}", response_model=List[VendorRankResult])
async def rank_vendors_for_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Run the multi-criteria vendor ranking ML model for a specific product.
    Returns suppliers ranked by composite score with recommendation labels:
    BEST CHOICE | LOWEST COST | FASTEST DELIVERY.
    """
    from app.models.inventory import ProductSupplier
    result = await db.execute(
        select(ProductSupplier, Supplier)
        .join(Supplier, ProductSupplier.supplier_id == Supplier.id)
        .where(ProductSupplier.product_id == product_id)
        .where(Supplier.is_active == True)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=404, detail="No active suppliers found for this product.")

    suppliers_data = [
        {
            "supplier_id": ps.supplier_id,
            "supplier_name": s.name,
            "reliability_score": float(s.reliability_score or 50),
            "avg_lead_time_days": float(s.avg_lead_time_days or 7),
            "defect_rate": float(s.defect_rate or 0.05),
            "avg_cost_index": float(s.avg_cost_index or 1.0),
            "supplier_price": float(ps.supplier_price or 0),
        }
        for ps, s in rows
    ]

    ranker = VendorRanker()
    ranked = ranker.rank(suppliers_data)
    return ranked


# ── Purchase Orders ──────────────────────────────────────────────────
@router.get("/orders", response_model=List[PurchaseOrderOut])
async def list_orders(
    status: Optional[str] = Query(None),
    supplier_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List purchase orders with optional status and supplier filters."""
    q = select(PurchaseOrder)
    if status:
        q = q.where(PurchaseOrder.status == status)
    if supplier_id:
        q = q.where(PurchaseOrder.supplier_id == supplier_id)
    q = q.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/orders", response_model=PurchaseOrderOut, status_code=201)
async def create_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Create a new purchase order.
    Validates delivery_city against serviceable_cities master list.
    Calculates total_amount from line items.
    """
    if payload.delivery_city not in settings.serviceable_cities:
        raise HTTPException(
            status_code=400,
            detail=f"'{payload.delivery_city}' is not a serviceable city. Allowed: {settings.serviceable_cities}",
        )

    import datetime
    item = payload.items[0] if payload.items else None
    if not item:
        raise HTTPException(status_code=400, detail="Order must have at least one item.")
    
    order = PurchaseOrder(
        supplier_id=payload.supplier_id,
        warehouse_id=1,  # Default warehouse
        product_id=item.product_id,
        order_date=datetime.datetime.utcnow().isoformat(),
        expected_delivery=payload.expected_delivery_date,
        quantity=item.quantity,
        unit_cost=float(item.unit_price or 0),
        status="Draft",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/orders/{order_id}", response_model=PurchaseOrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return order


# ── Procurement Decision (Approve/Override) ───────────────────────────
@router.post("/order", response_model=ProcurementDecisionOut, status_code=201)
async def submit_procurement_decision(
    payload: ProcurementDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_procurement),
):
    """
    Submit a procurement approval decision.
    - APPROVED: order advances to APPROVED status.
    - REJECTED: order is cancelled.
    - OVERRIDE: human overrides system recommendation; override_reason is required.
    Logs full audit trail to procurement_decisions ledger.
    """
    if payload.override_flag and not payload.override_reason:
        raise HTTPException(status_code=400, detail="override_reason is required when override_flag is True.")

    order = await db.get(PurchaseOrder, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")

    # Update order status
    if payload.decision == "APPROVED":
        order.status = "APPROVED"
    elif payload.decision == "REJECTED":
        order.status = "CANCELLED"
    # OVERRIDE keeps order as APPROVED but logs the override

    decision = ProcurementDecision(
        po_id=payload.order_id,
        decision_taken_by=current_user.id,
        override_flag=payload.override_flag,
        override_reason=payload.override_reason,
        ai_recommendation_score=float(payload.system_recommendation.split("Score: ")[1]) if payload.system_recommendation and "Score: " in payload.system_recommendation else None,
        recommended_supplier_id=order.supplier_id,
        selected_supplier_id=order.supplier_id
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return decision


@router.get("/decisions", response_model=List[ProcurementDecisionOut])
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all procurement decisions (audit log)."""
    result = await db.execute(select(ProcurementDecision).order_by(ProcurementDecision.decided_at.desc()))
    return result.scalars().all()
