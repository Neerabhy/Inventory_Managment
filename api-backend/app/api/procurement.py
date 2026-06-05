"""
api/procurement.py — Procurement routes: suppliers, purchase orders, vendor ranking, decisions.
"""
from __future__ import annotations

import datetime
import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .deps import get_current_user, get_db, require_procurement
from ..core.config import settings
from ..models.auth import User
from ..models.inventory import Inventory, Product, ProductSupplier
from ..models.predictions import SalesFeature, VendorRecommendation
from ..models.procurement import ProcurementDecision, PurchaseOrder, Supplier
from ..services.prediction_service import consume_vendor_recommendations, refresh_vendor_recommendations
from ..schemas.procurement import (
    ProcurementDecisionCreate,
    ProcurementDecisionOut,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    VendorRankResult,
)
from ..models.analytics import Return, Review, Sale


router = APIRouter(prefix="/procurement", tags=["Procurement"])


def _parse_date(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo:
            return parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


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
    refresh: bool = Query(False),
    warehouse_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _vendor_recommendations_response(product_id, refresh, db, warehouse_id)


async def _vendor_recommendations_response(
    product_id: int,
    refresh: bool,
    db: AsyncSession,
    warehouse_id: Optional[int] = None,
) -> List[VendorRankResult]:
    if refresh:
        feat = await db.scalar(select(SalesFeature).where(SalesFeature.product_id == product_id))
        inv_query = select(Inventory).where(Inventory.product_id == product_id)
        if warehouse_id is not None:
            inv_query = inv_query.where(Inventory.warehouse_id == warehouse_id)
        inv = await db.scalar(inv_query)
        avg_daily = float(feat.avg_daily_sales_30d if feat else 0.01)
        stock = int(inv.current_stock if inv else 0)
        await refresh_vendor_recommendations(db, product_id, avg_daily, stock)
        await db.flush()

    res = await db.execute(
        select(VendorRecommendation)
        .where(
            VendorRecommendation.product_id == product_id,
            VendorRecommendation.status == "ACTIVE",
        )
        .order_by(VendorRecommendation.rank_position)
    )
    rows = res.scalars().all()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No recommendations. Run demand forecast first or pass refresh=true.",
        )

    supplier_ids = [r.supplier_id for r in rows]
    suppliers_by_id = {}
    if supplier_ids:
        supplier_rows = (
            await db.execute(select(Supplier).where(Supplier.id.in_(supplier_ids)))
        ).scalars().all()
        suppliers_by_id = {supplier.id: supplier for supplier in supplier_rows}

    warehouse_city = await _warehouse_city(db, warehouse_id)
    enriched = []
    for r in rows:
        supplier = suppliers_by_id.get(r.supplier_id)
        supplier_city = supplier.city if supplier else None
        shipping = await _lane_estimate(db, supplier_city, warehouse_city)
        supplier_price = float(r.supplier_price or 0)
        shipping_cost = float(shipping["shipping_cost"] or 0)
        delivery_time = float(shipping["delivery_time_days"] or r.lead_time_days or 0)
        lead_time = int(math.ceil(delivery_time)) if delivery_time else int(r.lead_time_days or 0)
        landed_cost = supplier_price + shipping_cost
        score = float(r.adjusted_score or r.composite_score or 0)
        if warehouse_city:
            score = max(0, min(1, score - min(shipping_cost / 10000, 0.08) - min(delivery_time / 100, 0.05)))
        enriched.append(
            VendorRankResult(
            supplier_id=r.supplier_id,
            supplier_name=r.supplier_name or "",
            composite_score=score,
            recommendation=r.recommendation or "RECOMMENDED",
            reliability_score=supplier.reliability_score if supplier else 0,
            avg_lead_time_days=float(r.lead_time_days or 0),
            defect_rate=supplier.defect_rate if supplier else 0,
            avg_cost_index=supplier.avg_cost_index if supplier else float(r.supplier_price or 0),
            supplier_risk_label=r.supplier_risk_label,
            supplier_price=supplier_price,
            lead_time_days=lead_time,
            supplier_city=supplier_city,
            warehouse_city=warehouse_city,
            shipping_cost=round(shipping_cost, 2),
            delivery_time_days=round(delivery_time, 1),
            landed_cost=round(landed_cost, 2),
            days_stock_covers=float(r.days_stock_covers or 0),
            avg_daily_demand=float(r.avg_daily_demand or 0),
            rank_position=int(r.rank_position or 0),
        )
        )
    enriched.sort(key=lambda vendor: (-(vendor.composite_score or 0), vendor.landed_cost or 0))
    for idx, vendor in enumerate(enriched, start=1):
        vendor.rank_position = idx
        if idx == 1 and warehouse_city:
            vendor.recommendation = "AI RECOMMENDED FOR THIS WAREHOUSE"
    return enriched


async def _warehouse_city(db: AsyncSession, warehouse_id: Optional[int]) -> Optional[str]:
    if not warehouse_id:
        return None
    row = (
        await db.execute(
            text("SELECT city FROM warehouses WHERE warehouse_id = :warehouse_id"),
            {"warehouse_id": warehouse_id},
        )
    ).mappings().first()
    return str(row["city"]) if row and row.get("city") else None


async def _lane_estimate(db: AsyncSession, supplier_city: Optional[str], warehouse_city: Optional[str]) -> dict:
    if not supplier_city or not warehouse_city:
        return {"shipping_cost": 0.0, "delivery_time_days": None}
    row = (
        await db.execute(
            text(
                """
                SELECT AVG(shipping_cost) AS shipping_cost,
                       AVG(expected_delivery_days) AS delivery_time_days
                FROM shipments
                WHERE lower(source_city) = lower(:source_city)
                  AND lower(destination_city) = lower(:destination_city)
                """
            ),
            {"source_city": supplier_city, "destination_city": warehouse_city},
        )
    ).mappings().first()
    if row and row.get("shipping_cost") is not None:
        return {
            "shipping_cost": float(row.get("shipping_cost") or 0),
            "delivery_time_days": float(row.get("delivery_time_days") or 0),
        }
    if supplier_city.lower() == warehouse_city.lower():
        return {"shipping_cost": 75.0, "delivery_time_days": 1.0}
    return {"shipping_cost": 175.0, "delivery_time_days": 4.0}


@router.get("/recommendations/{product_id}", response_model=List[VendorRankResult])
async def get_vendor_recommendations(
    product_id: int,
    refresh: bool = Query(False),
    warehouse_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _vendor_recommendations_response(product_id, refresh, db, warehouse_id)


@router.get("/suppliers/{supplier_id}/profile")
async def get_supplier_profile(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Comprehensive supplier profile: recent orders, products supplied, return stats, reviews summary.
    """
    

    # Get supplier
    s = await db.get(Supplier, supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found.")

    # Recent purchase orders
    orders_result = await db.execute(
        select(PurchaseOrder, Product)
        .join(Product, PurchaseOrder.product_id == Product.id)
        .where(PurchaseOrder.supplier_id == supplier_id)
        .order_by(PurchaseOrder.id.desc())
        .limit(10)
    )
    orders = orders_result.all()

    all_orders_result = await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.supplier_id == supplier_id)
    )
    all_orders = all_orders_result.scalars().all()
    open_statuses = {"Draft", "Pending", "Approved", "APPROVED", "In Transit", "Shipped"}
    current_orders = sum(1 for o in all_orders if (o.status or "") in open_statuses)
    delivery_durations = []
    for order in all_orders:
        ordered_at = _parse_date(order.order_date)
        delivered_at = _parse_date(order.actual_delivery)
        if ordered_at and delivered_at and delivered_at >= ordered_at:
            delivery_durations.append((delivered_at - ordered_at).days)
    avg_delivery_time_days = (
        round(sum(delivery_durations) / len(delivery_durations), 1)
        if delivery_durations
        else None
    )

    all_product_ids_result = await db.execute(
        select(ProductSupplier.product_id).where(ProductSupplier.supplier_id == supplier_id)
    )
    all_product_ids = [row[0] for row in all_product_ids_result.all()]

    # Products supplied via product_suppliers table
    ps_result = await db.execute(
        select(ProductSupplier, Product)
        .join(Product, ProductSupplier.product_id == Product.id)
        .where(ProductSupplier.supplier_id == supplier_id)
        .limit(20)
    )
    product_rows = ps_result.all()

    # Return stats for products from this supplier
    return_count = 0
    if all_product_ids:
        ret_result = await db.execute(
            select(func.count()).where(Return.product_id.in_(all_product_ids))
        )
        return_count = ret_result.scalar_one_or_none() or 0

    # Review summary
    avg_rating = None
    if all_product_ids:
        try:
            rat_result = await db.execute(
                select(func.avg(Review.rating)).where(Review.product_id.in_(all_product_ids))
            )
            avg_rating = rat_result.scalar_one_or_none()
        except Exception:
            avg_rating = None

    return {
        "supplier": {
            "id": s.id,
            "supplier_code": s.supplier_code,
            "name": s.name,
            "city": s.city,
            "state": s.state,
            "country": s.country,
            "reliability_score": s.reliability_score,
            "avg_lead_time_days": s.avg_lead_time_days,
            "on_time_delivery_rate": s.on_time_delivery_rate,
            "defect_rate": s.defect_rate,
            "avg_cost_index": s.avg_cost_index,
            "payment_terms": s.payment_terms,
            "minimum_order_qty": s.minimum_order_qty,
            "supplier_specialization": s.supplier_specialization,
            "is_active": s.is_active,
        },
        "recent_orders": [
            {
                "id": o.id,
                "po_code": o.po_code,
                "product_id": o.product_id,
                "product_name": p.product_name,
                "sku": p.sku,
                "quantity": o.quantity,
                "status": o.status,
                "order_date": o.order_date,
                "expected_delivery": o.expected_delivery,
                "unit_cost": o.unit_cost,
                "total_amount": o.total_amount,
                "warehouse_id": o.warehouse_id,
            }
            for o, p in orders
        ],
        "products_supplied": [
            {
                "product_id": ps.product_id,
                "product_name": p.product_name,
                "sku": p.sku,
                "category": p.category,
                "supplier_price": ps.supplier_price,
                "lead_time_days": ps.lead_time_days,
                "preferred": bool(ps.preferred_supplier_flag),
                "contract_status": ps.contract_status,
            }
            for ps, p in product_rows
        ],
        "stats": {
            "total_orders": len(all_orders),
            "current_orders": current_orders,
            "avg_delivery_time_days": avg_delivery_time_days,
            "products_count": len(all_product_ids),
            "return_count": int(return_count),
            "avg_product_rating": round(float(avg_rating), 2) if avg_rating else None,
        },
    }


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
    await consume_vendor_recommendations(db, item.product_id)
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
